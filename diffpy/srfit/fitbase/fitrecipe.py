#!/usr/bin/env python
########################################################################
#
# diffpy.srfit      by DANSE Diffraction group
#                   Simon J. L. Billinge
#                   (c) 2008 Trustees of the Columbia University
#                   in the City of New York.  All rights reserved.
#
# File coded by:    Chris Farrow
#
# See AUTHORS.txt for a list of people who contributed.
# See LICENSE.txt for license information.
#
########################################################################
"""FitRecipe class. 

FitRecipes organize FitContributions, variables, Restraints and Constraints to
create a recipe of the system you wish to optimize. From the client's
perspective, the FitRecipe is a residual calculator. The residual method does
the work of updating variable values, which get propagated to the Parameters of
the underlying FitContributions via the Varibles, Restraints and Constraints.
This class needs no special knowledge of the type of FitContribution or data
being used. Thus, it is suitable for combining residual equations from various
types of refinements into a single residual.

See the examples in the documentation for how to create an optimization problem
using FitRecipe.

"""

from numpy import concatenate, sqrt, inf, dot

from diffpy.srfit.util.ordereddict import OrderedDict
from .parameter import ParameterProxy
from .recipeorganizer import RecipeOrganizer
from .fithook import FitHook

class FitRecipe(RecipeOrganizer):
    """FitRecipe class.

    Attributes
    clicker         --  A Clicker instance for recording changes in contained
                        Parameters and FitContributions.
    name            --  A name for this FitRecipe.
    fithook         --  An object to be called whenever within the residual
                        (default FitHook()) that can pass information out of
                        the system during a refinement.
    _constraintlist --  An ordered list of the constraints from this and all
                        sub-components.
    _constraints    --  A dictionary of Constraints, indexed by the constrained
                        Parameter. Constraints can be added using the
                        'constrain' method.
    _calculators    --  A managed dictionary of Calculators.
    _contributions  --  A managed OrderedDict of FitContributions.
    _parameters     --  A managed OrderedDict of parameters (in this case the
                        parameters are varied).
    _restraints     --  A set of Restraints. Restraints can be added using the
                        'restrain' or 'confine' methods.
    _eqfactory      --  A diffpy.srfit.equation.builder.EquationFactory
                        instance that is used to create constraints and
                        restraints from string
    _doprepare      --  A flag indicating that the the attributes need to be
                        prepared for calculation.
    _fixed          --  A set of parameters that are not actually varied.
    _restraintlist  --  A list of restraints from this and all sub-components.
    _restraints     --  A set of Restraints. Restraints can be added using the
                        'restrain' or 'confine' methods.
    _tagdict        --  A dictionary of tags to variables.
    _weights        --  List of weighing factors for each FitContribution. The
                        weights are multiplied by the residual of the
                        FitContribution when determining the overall residual.

    """

    def __init__(self, name = "fit"):
        """Initialization."""
        RecipeOrganizer.__init__(self, name)
        self.fithook = FitHook()
        self._constraintlist = []
        self._restraintlist = []

        self._weights = []
        self._doprepare = True
        self._tagdict = {}

        self._fixed = set()

        self._contributions = OrderedDict()
        self._manage(self._contributions)
        return

    def setFitHook(self, fithook):
        """Set a hook to be called within the residual method.

        The hook is an object for reportind updates, or more fundamentally,
        passing information out of the system during a refinement. It must have
        'precall' and 'postcall' methods, which are called at the start and at
        the end of the residual calculation. The precall method must accept a
        single argument, which is this FitRecipe object. The postcall method
        must accept the recipe and the chiv, vector residual.  It must also
        have a reset method that takes no arguments, which is called whenver
        the FitRecipe is prepared for a refinement.

        See the FitHook class for the interface.

        """
        self.fithook = fithook
        self._doprepare = True
        return

    def addContribution(self, con, weight = 1.0):
        """Add a FitContribution to the FitRecipe.

        con     --  The FitContribution to be stored.

        Raises ValueError if the FitContribution has no name
        Raises ValueError if the FitContribution has the same name as some
        other managed object.
        
        """
        self._addObject(con, self._contributions, True)
        self._weights.append(weight)
        self._doprepare = True
        return

    def setWeight(self, con, weight):
        """Set the weight of a FitContribution."""
        idx = self._contributions.values().index(con)
        self._weights[idx] = weight
        return

    def residual(self, p = []):
        """Calculate the residual to be optimized.

        Arguments
        p   --  The list of current variable values, provided in the same order
                as the '_parameters' list. If p is an empty iterable (default),
                then it is assumed that the parameters have already been
                updated in some other way, and the explicit update within this
                function is skipped.

        The residual is by default the weighted concatenation of each 
        FitContribution's residual, plus the value of each restraint. The array
        returned, denoted chiv, is such that 
        dot(chiv, chiv) = chi^2 + restraints.

        """

        if self._doprepare:
            self._prepare()

        if self.fithook:
            self.fithook.precall(self)

        # Update the variable parameters.
        self.__applyValues(p)

        # Update the constraints. These are ordered such that the list only
        # needs to be cycled once.
        for con in self._constraintlist:
            con.update()

        # Calculate the bare chiv
        chiv = concatenate([ 
            sqrt(self._weights[i])*self._contributions.values()[i].residual() \
                    for i in range(len(self._contributions))])

        # Calculate the point-average chi^2
        w = dot(chiv, chiv)/len(chiv)
        # Now we must append the restraints
        penalties = [ sqrt(res.penalty(w)) for res in self._restraintlist ]
        chiv = concatenate( [ chiv, penalties ] )

        if self.fithook:
            self.fithook.postcall(self, chiv)

        return chiv

    def scalarResidual(self, p = []):
        """A scalar version of the residual.

        See the residual method. This returns dot(chiv, chiv).

        """
        chiv = self.residual(p)
        return dot(chiv, chiv)

    def _prepare(self):
        """Prepare for the calculation.

        This will prepare the data attributes to be used in the residual
        calculation.

        This updates the local constraints and restraints with those of the
        contributions.

        Constraints can have inter-dependencies that require that they are
        updated in a specific order. This will set the proper order.

        Raises AttributeError if there are variables without a value.
        Raises AttributeError if there are multiple constraints on the same
        parameter defined in different places within the recipe hierarchy.

        """

        # Inform the fit hook that we're updating things
        if self.fithook:
            self.fithook.reset()

        # Check Profiles
        self.__verifyProfiles()

        # Check variables
        self.__verifyVariables()

        # Update constraints and restraints. 
        self.__collectConstraintsAndRestraints()

        # We're done here
        self._doprepare = False
        return


    def __verifyProfiles(self):
        """Verify that each FitContribution has a Profile."""
        # Check for profile values
        for con in self._contributions.values():
            if con.profile is None:
                m = "FitContribution '%s' does not have a Profile"%con.name
                raise AttributeError(m)
            if con.profile.x is None or\
                con.profile.y is None or\
                con.profile.dy is None:

                    m = "Profile for '%s' is missing data"%con.name
                    raise AttributeError(m)

        return

    def __verifyVariables(self):
        """Verify that all variables have values."""

        names = self.getNames()
        m = ""
        badvars = []
        for idx, val in enumerate(self.getValues()):
            if val is not None: continue
            badvars.append( "'%s'"%names[idx] )

        if len(badvars) == 1:
            m = "variable %s needs an initial value" % badvars[0]
        elif len(badvars) > 0:
            s1 = ",".join(badvars[:-1])
            s2 = badvars[-1]
            m = "variables %s and %s need initial values" % (s1, s2)

        if m:
            raise AttributeError(m)

        return

    def __collectConstraintsAndRestraints(self):
        """Collect the Constraints and Restraints from subobjects."""
        rset = set(self._restraints)
        cdict = {}
        # We let constraints closer to the FitRecipe override all others.
        # Constraints on the same parameter in different organizers cannot be
        # resolved without some guesswork, so throw an error instead.
        for con in self._contributions.values():
            rset.update( con._getRestraints() )
            constraints = con._getConstraints()
            pars = set(cdict.keys()).intersection( constraints.keys() )
            if pars:
                m = "There are multiple internal constraints on '%s'"%\
                        pars.pop()
                raise AttributeError(m)
            cdict.update(constraints)
        # Update with local constraints last
        cdict.update(self._constraints)

        # Reorder the constraints. Constraints are ordered such that a given
        # constraint is placed before its dependencies.

        self._restraintlist = list(rset)
        self._constraintlist = cdict.values()

        # Create a depth-1 map of the constraint dependencies
        depmap = {}
        for con in self._constraintlist:
            depmap[con] = set()
            # Now check the constraint's equation for constrained arguments
            for arg in con.eq.args:
                if arg in self._constraintlist:
                    depmap[con].add( arg )

        # Turn the dependency map into multi-level map.
        def _extendDeps(con):
            deps = set(depmap[con])
            for dep in depmap[con]:
                deps.update(_extendDeps(dep))

            return deps

        for con in depmap:
            depmap[con] = _extendDeps(con)

        # Now sort the constraints based on the dependency map
        def cmp(x, y):
            # If y is a dependency of x, then y must come first
            if y in depmap[x]:
                return 1
            # If x is a dependency of y, then x must come first
            if x in depmap[y]:
                return -1
            # Otherwise, these are equivalant
            return 0

        self._constraintlist.sort(cmp)

        return


    # Variable manipulation

    def addVar(self, par, value = None, name = None, fixed = False, tag = None,
            tags = []):
        """Add a variable to be refined.

        par     --  A Parameter that will be varied during a fit.
        value   --  An initial value for the variable. If this is None
                    (default), then the current value of par will be used.
        name    --  A name for this variable. If name is None (default), then
                    the name of the parameter will be used.
        fixed   --  Fix the variable so that it does not vary (default False).
        tag     --  A tag for the variable. This can be used to fix and free
                    variables by tag (default None).
        tags    --  A list of tags (default []). Both tag and tags can be
                    applied.

        Returns the ParameterProxy (variable) for the passed Parameter.

        Raises ValueError if the name of the variable is already taken by
        another managed object.
        Raises ValueError if par is constant.

        """
        name = name or par.name

        if par.const:
            raise ValueError("The parameter '%s' is constant"%par)

        var = ParameterProxy(name, par)
        if value is not None:
            var.setValue(value)

        self._addParameter(var)

        if fixed:
            self.fixVar(var)
          
        # Deal with tags
        self.__applyTags(var, tag, tags)

        self._doprepare = True

        return var

    def __applyTags(self, var, tag, tags):
        """Apply tags to a variable.

        tag     --  A tag for the variable. This can be used to fix and free
                    variables by tag (default None).
        tags    --  A list of tags (default []). Both tag and tags can be
                    applied.

        """
        if tag:
            self.__tagVar(var, tag)

        for t in tags:
            self.__tagVar(var, tag)

        return

    def __tagVar(self, var, tag):
        """Private function to tag a variable."""
        vset = self._tagdict.get(tag, set())
        vset.add(var)
        self._tagdict[tag] = vset
        return

    def delVar(self, var):
        """Remove a variable.

        var     --  A variable of the FitRecipe.

        Raises ValueError if var is not part of the FitRecipe.

        """

        self._removeParameter(var)
        self._fixed.discard(var)

        # Remove tags
        for vset in self._tagdict.items():
            vset.discard(var)
        
        return

    def newVar(self, name, value, fixed = False, tag = None, tags = []):
        """Create a new variable of the fit.

        This method lets new variables be created that are not tied to a
        Parameter.  Orphan variables may cause a fit to fail, depending on the
        optimization routine, and therefore should only be created to be used
        in contraint or restraint equations.

        name    --  The name of the variable. The variable will be able to be
                    used by this name in restraint and constraint equations.
        value   --  An initial value for the variable. 
        fixed   --  Fix the variable so that it does not vary (default False).
        tag     --  A tag for the variable. This can be used to fix and free
                    variables by tag (default None).
        tags    --  A list of tags (default []). Both tag and tags can be
                    applied.

        Returns the new variable (Parameter instance).

        """
        var = self._newParameter(name, value)

        if fixed:
            self.fixVar(var)

        # Deal with tags
        self.__applyTags(var, tag, tags)

        self._doprepare = True
        return var

    def fixVar(self, var, value = None):
        """Fix a variable so that it doesn't change.

        var     --  A variable of the FitRecipe.
        value   --  A new value for the variable. If this is None
                    (default), then the value will not be changed.

        """
        self._fixed.add(var)

        if value is not None:
            var.setValue(value)

        return

    def freeVar(self, var, value = None):
        """Free a variable so that it is refined.

        Variables are free by default.

        var     --  A variable of the FitRecipe.
        value   --  A new value for the variable. If this is None
                    (default), then the value will not be changed.

        """
        self._fixed.discard(var)

        if value is not None:
            var.setValue(value)

        return

    def fixAll(self, *tags):
        """Fix all variables.

        Extra arguments are assumed to be tags. If present, only variables with
        the given tag will be fixed.

        """

        tagset = self.__getTagSet(tags)

        if tagset:
            self._fixed.update(tagset)
        else:
            self._fixed.update(self._parameters.values())

        return

    def freeAll(self, *tags):
        """Free all variables.

        Extra arguments are assumed to be tags. If present, only variables with
        the given tag will be fixed.

        """
        tagset = self.__getTagSet(tags)

        if tagset:
            self._fixed.difference_update(tagset)
        else:
            self._fixed.clear()

        return

    def __getTagSet(self, *tags):
        """Get all variables with the given tags."""
        tagset = set()
        for tag in tags:
            tagset.update( self._tagdict.get(tag, []) )
        return tagset

    def getValues(self):
        """Get the current values of the variables in a list."""
        return [par.getValue() for par in self._parameters.values() if par not
                in self._fixed]

    def getNames(self):
        """Get the names of the variables in a list."""
        return [par.name for par in self._parameters.values() if par not in
                self._fixed]

    def __applyValues(self, p):
        """Apply variable values to the variables."""
        if len(p) == 0: return
        vars = [v for v in self._parameters.values() if v not in self._fixed]
        for var, pval in zip(vars, p):
            var.setValue(pval)
        return


    # These must set _doprepare = True

    def constrain(self, par, con, ns = {}):
        """Constrain a parameter to an equation.

        Note that only one constraint can exist on a Parameter at a time. The
        most recent constraint override all other user-defined constraints.
        Built-in constraints override all other constraints.

        par     --  The Parameter to constrain. It does not need to be a
                    variable.
        con     --  A string representation of the constraint equation or a
                    parameter to constrain to.  A constraint equation must
                    consist of numpy operators and "known" Parameters.
                    Parameters are known if they are in the ns argument, or if
                    they have been added to this FitRecipe with the 'add' or
                    'new' methods.
        ns      --  A dictionary of Parameters, indexed by name, that are used
                    in the eqstr, but not part of the FitRecipe (default {}).

        Raises ValueError if ns uses a name that is already used for a
        variable.
        Raises ValueError if eqstr depends on a Parameter that is not part of
        the FitRecipe and that is not defined in ns.

        """
        RecipeOrganizer.constrain(self, par, con, ns)
        self._doprepare = True
        return

    def unconstrain(self, par):
        """Unconstrain a Parameter.

        par     --  The Parameter to unconstrain.

        This removes any constraints on a parameter, including built-in
        constraints.

        """
        RecipeOrganizer.unconstrain(self, par)
        self._doprepare = True
        return

    def restrain(self, res, lb = -inf, ub = inf, prefactor = 1, power = 2,  
            scaled = False, ns = {}):
        """Restrain an expression to specified bounds

        res     --  An equation string or Parameter to restrain.
        lb      --  The lower bound on the restraint evaluation (default -inf).
        ub      --  The lower bound on the restraint evaluation (default inf).
        prefactor   --  A multiplicative prefactor for the restraint 
                        (default 1).
        power   --  The power of the penalty (default 2).
        scaled  --  A flag indicating if the restraint is scaled (multiplied)
                    by the unrestrained point-average chi^2 (chi^2/numpoints)
                    (default False).
        ns      --  A dictionary of Parameters, indexed by name, that are used
                    in the eqstr, but not part of the FitRecipe 
                    (default {}).

        The penalty is calculated as 
        prefactor * max(0, lb - val, val - ub) ** power
        and val is the value of the calculated equation. This is multipled by
        the average chi^2 if scaled is True.

        Raises ValueError if ns uses a name that is already used for a
        Parameter.
        Raises ValueError if eqstr depends on a Parameter that is not part of
        the FitRecipe and that is not defined in ns.

        Returns the Restraint selfect for use with the 'unrestrain' method.

        """
        res = RecipeOrganizer.restrain(self, res, lb, ub, prefactor, power,
                scaled, ns)
        self._doprepare = True
        return res

    def confine(self, res, lb = -inf, ub = inf, ns = {}):
        """Confine an expression to hard bounds.

        res     --  An equation string or Parameter to restrain.
        lb      --  The lower bound on the restraint evaluation (default -inf).
        ub      --  The lower bound on the restraint evaluation (default inf).
        ns      --  A dictionary of Parameters, indexed by name, that are used
                    in the eqstr, but not part of the FitRecipe 
                    (default {}).

        The penalty is infinite if the value of the calculated equation is
        outside the bounds.

        Raises ValueError if ns uses a name that is already used for a
        Parameter.
        Raises ValueError if eqstr depends on a Parameter that is not part of
        the FitRecipe and that is not defined in ns.

        Returns the BoundsRestraint object for use with the 'unrestrain' method.

        """
        res = RecipeOrganizer.confine(self, res, lb, ub, ns)
        self._doprepare = True
        return res

    def unrestrain(self, res):
        """Remove a restraint from the FitRecipe.
        
        res     --  A Restraint returned from the 'restrain' method.

        """
        RecipeOrganizer.unrestrain(self, res)
        self._doprepare = True
        return

# Decorator to apply _doprepare = True
def setprepare(f):

    def _f(self, *args, **kw):
        self._doprepare = True
        return f(self, *args, **kw)

    _f.__doc__ = f.__doc__

    return _f



# version
__id__ = "$Id$"

#
# End of file
