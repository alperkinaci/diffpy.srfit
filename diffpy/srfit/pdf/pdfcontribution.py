#!/usr/bin/env python
########################################################################
#
# diffpy.srfit      by DANSE Diffraction group
#                   Simon J. L. Billinge
#                   (c) 2010 Trustees of the Columbia University
#                   in the City of New York.  All rights reserved.
#
# File coded by:    Chris Farrow
#
# See AUTHORS.txt for a list of people who contributed.
# See LICENSE.txt for license information.
#
########################################################################
"""PDFContribution class. 

This is a custom FitContribution that simplifies the creation of PDF fits.

"""
__all__ = ["PDFContribution"]

from diffpy.srfit.fitbase import FitContribution
from diffpy.srfit.fitbase import Profile

class PDFContribution(FitContribution):
    """PDFContribution class.

    PDFContribution is a FitContribution that is customized for PDF fits. Data
    and phases can be added directly to the PDFContribution. Setup of
    constraints and restraints requires direct interaction with the generator
    attributes (see setPhase).

    Attributes
    name            --  A name for this FitContribution.
    profile         --  A Profile that holds the measured (and calcuated)
                        signal.
    _meta           --  Metadata dictionary. This is specific to this object,
                        and not shared with the profile. This is used to record
                        configuration options, like qmax.
    _calculators    --  A managed dictionary of Calculators, indexed by name.
    _constraints    --  A set of constrained Parameters. Constraints can be
                        added using the 'constrain' methods.
    _generators     --  A managed dictionary of ProfileGenerators.
    _parameters     --  A managed OrderedDict of parameters.
    _restraints     --  A set of Restraints. Restraints can be added using the
                        'restrain' or 'confine' methods.
    _parsets        --  A managed dictionary of ParameterSets.
    _eqfactory      --  A diffpy.srfit.equation.builder.EquationFactory
                        instance that is used to create constraints and
                        restraints from string
    _eq             --  The FitContribution equation that will be optimized.
    _reseq          --  The residual equation.
    _xname          --  Name of the x-variable
    _yname          --  Name of the y-variable
    _dyname         --  Name of the dy-variable

    Managed Parameters:
    scale   --  Scale factor
    qbroad  --  Resolution peak broadening term
    qdamp   --  Resolution peak dampening term

    """

    def __init__(self, name):
        """Create the PDFContribution.

        name        --  The name of the contribution.

        """
        FitContribution.__init__(self, name)
        self._meta = {}
        # Add the profile
        profile = Profile()
        self.setProfile(profile, xname = "r")

        # Need a parameter for the overall scale, in the case that this is a
        # multi-phase fit.
        self.newParameter("scale", 1.0)
        # Profile-related parameters that will be shared between the generators
        self.newParameter("qdamp", 0)
        self.newParameter("qbroad", 0)
        return

    # Data methods

    def loadData(self, data):
        """Load the data in various formats.

        This uses the PDFParser to load the data and then passes it to the
        build-in profile with loadParsedData.

        data    --  An open file-like object, name of a file that contains data
                    or a string containing the data.

        """
        # Get the data into a string
        from diffpy.srfit.util.inpututils import inputToString
        datstr = inputToString(data)

        # Load data with a PDFParser
        from diffpy.srfit.pdf.pdfparser import PDFParser
        parser = PDFParser()
        parser.parseString(datstr)

        # Pass it to the profile
        self.profile.loadParsedData(parser)
        return

    def setCalculationRange(self, xmin = None, xmax = None, dx = None):
        """Set the calculation range

        This calls on the built-in Profile.

        Arguments
        xmin    --  The minimum value of the independent variable.
                    If xmin is None (default), the minimum observed value will
                    be used. This is clipped to the minimum observed x.
        xmax    --  The maximum value of the independent variable.
                    If xmax is None (default), the maximum observed value will
                    be used. This is clipped to the maximum observed x.
        dx      --  The sample spacing in the independent variable. If dx is
                    None (default), then the spacing in the observed points
                    will be preserved.

        Note that xmin is always inclusive (unless clipped). xmax is inclusive
        if it is within the bounds of the observed data.

        raises AttributeError if there is no observed profile
        raises ValueError if xmin > xmax
        raises ValueError if dx > xmax-xmin
        raises ValueError if dx <= 0

        """
        return self.profile.setCalculationRange(xmin, xmax, dx)

    def savetxt(self, fname, fmt='%.18e', delimiter=' '):
        """Call numpy.savetxt with x, ycalc, y, dy

        This calls on the built-in Profile.

        Arguments are passed to numpy.savetxt. 

        """
        return self.profile.savetxt(fname, fmt, delimiter)

    # Phase methods

    def addPhase(self, name, stru = None, parset = None, periodic = True):
        """Add a phase that goes into the PDF calculation.

        name    --  A name to give the generator that will manage the PDF
                    calculation from the passed structure. The adapted
                    structure will be accessible via the name "phase" as an
                    attribute of the generator, e.g.
                    contribution.name.phase, where 'contribution' is this
                    contribution and 'name' is passed name.
                    (default), then the name will be set as "phase".
        stru    --  diffpy.Structure.Structure, pyobjcryst.crystal.Crystal or
                    pyobjcryst.molecule.Molecule instance . Default None.
        parset  --  A ParameterSet that holds the structural information. This
                    can be used to share the phase between multiple
                    PDFGenerators, and have the changes in one reflect in
                    another. If both stru and parset are specified, only parset
                    is used. Default None. 
        periodic -- The structure should be treated as periodic.  If this is
                    True (default), then a PDFGenerator will be used to
                    calculate the PDF from the phase. Otherwise, a
                    DebyePDFGenerator will be used. Note that some structures
                    do not support periodicity, in which case this may be
                    ignored.

        Raises ValueError if neither stru nor parset is specified.

        Returns the new phase (ParameterSet appropriate for what was passed in
        stru.)

        """
        from diffpy.srfit.pdf.pdfgenerator import PDFGenerator
        from diffpy.srfit.pdf.debyepdfgenerator import DebyePDFGenerator
        # Based on periodic, create the proper generator.
        if periodic:
            gen = PDFGenerator(name)
        else:
            gen = DebyePDFGenerator(name)
        self.addProfileGenerator(gen)

        # Set up the generator
        gen.setPhase(stru, "phase", parset, periodic)

        # Set the proper equation for the fit, depending on the number of
        # phases we have.
        gnames = self._generators.keys()
        eqstr = " + ".join(gnames)
        eqstr = "scale * (%s)" % eqstr
        self.setEquation(eqstr)

        # Update with our metadata
        gen.meta.update(self._meta)
        gen.processMetaData()

        # Constrain the shared parameters
        self.constrain(gen.qdamp, self.qdamp)
        self.constrain(gen.qbroad, self.qbroad)
        return gen.phase

    # Calculation setup methods

    def _getMetaValue(self, kwd):
        """Get metadata according to object hierarchy."""
        # Check self, then generators then profile
        val = self._meta.get("kwd")
        if val is None and len(self._generators) > 0:
            gen = self._generators.values()[0]
            val = gen.meta.get(kwd)
        else:
            val = self.profile.meta.get(kwd)
        return val

    def setScatteringType(self, type = "X"):
        """Set the scattering type.
        
        type    --   "X" for x-ray or "N" for neutron

        Raises ValueError if type is not "X" or "N"

        """
        self._meta["stype"] = type
        for gen in self._generators.values():
            gen.setScatteringType(type)
        return
    
    def getScatteringType(self):
        """Get the scattering type. See 'setScatteringType'."""
        return self._getMetaValue("stype")

    def setQmax(self, qmax):
        """Set the qmax value."""
        self._meta["qmax"] = qmax
        for gen in self._generators.values():
            gen.setQmax(qmax)
        return

    def getQmax(self):
        """Get the qmax value."""
        return self._getMetaValue("qmax")

    def setQmin(self, qmin):
        """Set the qmin value.

        This has no effect on the crystal PDF.
        
        """
        self._meta["qmin"] = qmin
        for gen in self._generators.values():
            gen.setQmin(qmin)
        return

    def getQmin(self):
        """Get the qmin value."""
        return self._getMetaValue("qmax")

# version
__id__ = "$Id$"

#
# End of file
