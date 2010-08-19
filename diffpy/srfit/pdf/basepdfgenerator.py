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
"""PDF profile generator base class.

The BasePDFGenerator class interfaces with SrReal PDF calculators and is used
as a base for the PDFGenerator and DebyePDFGenerator classes.

"""
__all__ = ["BasePDFGenerator"]

import numpy

from diffpy.srfit.fitbase import ProfileGenerator
from diffpy.srfit.fitbase.parameter import ParameterAdapter
from diffpy.srfit.structure import struToParameterSet

# FIXME - Parameter creation will have to be smarter once deeper calculator
# configuration is enabled.
# FIXME - Need to decouple the non-structural parameters from the
# diffpy.Structure object, otherwise, we can't share the structural
# ParameterSet between different Generators.

class BasePDFGenerator(ProfileGenerator):
    """Base class for calculating PDF profiles using SrReal.

    This works with diffpy.Structure.Structure, pyobjcryst.crystal.Crystal and
    pyobjcryst.molecule.Molecule instances. Note that the managed Parameters
    are not created until the structure is added.

    Attributes:
    _calc   --  PDFCalculator or DebyePDFCalculator instance for calculating
                the PDF
    _phase  --  The structure ParameterSet used to calculate the profile.
    _lastr  --  The last value of r over which the PDF was calculated. This is
                used to configure the calculator when r changes.
    _ncpu   --  The number of cpus to use for the calculation.
    _pool   --  A multiprocessing.Pool for managing parallel computation.

    Managed Parameters:
    scale   --  Scale factor
    delta1  --  Linear peak broadening term
    delta2  --  Quadratic peak broadening term
    qbroad  --  Resolution peak broadening term
    qdamp   --  Resolution peak dampening term

    Managed ParameterSets:
    The structure ParameterSet (BaseStructure instance) used to calculate the
    profile is named by the user.

    Usable Metadata:
    stype   --  The scattering type "X" for x-ray, "N" for neutron (see
                'setScatteringType').
    qmax    --  The maximum scattering vector used to generate the PDF (see
                setQmax).
    qmin    --  The minimum scattering vector used to generate the PDF (see
                setQmin).
    scale   --  See Managed Parameters.
    delta1  --  See Managed Parameters.
    delta2  --  See Managed Parameters.
    qbroad  --  See Managed Parameters.
    qdamp   --  See Managed Parameters.

    """

    def __init__(self, name = "pdf"):
        """Initialize the generator."""
        ProfileGenerator.__init__(self, name)

        self._phase = None
        self.meta = {}
        self._lastr = None
        self._calc = None

        self._ncpu = 1
        self._pool = None

        return

    def parallel(self, ncpu):
        """Run calculation in parallel."""
        if ncpu <= 1: return
        import multiprocessing
        self._ncpu = min(ncpu, multiprocessing.cpu_count())
        self._pool = multiprocessing.Pool(self._ncpu)
        return

    def processMetaData(self):
        """Process the metadata once it gets set."""
        ProfileGenerator.processMetaData(self)
        stype = self.meta.get("stype")
        if stype is not None:
            self.setScatteringType(stype)

        qmax = self.meta.get("qmax")
        if qmax is not None:
            self.setQmax(qmax)

        parnames = ['delta1', 'delta2', 'qbroad', 'qdamp']

        for name in parnames:
            val = self.meta.get(name)
            if val is not None:
                par = self.get(name)
                par.setValue(val)

        scale = self.meta.get('scale')
        if scale is not None:
            self.scale.setValue(scale)

        return

    def setScatteringType(self, type = "X"):
        """Set the scattering type.
        
        type    --   "X" for x-ray or "N" for neutron

        Raises ValueError if type is not "X" or "N"

        """
        type = type.upper()
        if type not in ("X", "N"):
            raise ValueError("Unknown scattering type '%s'"%type)

        self.meta["stype"] = type

        self._calc.setScatteringFactorTableByType(type)

        return
    
    def getScatteringType(self):
        """Get the scattering type. See 'setScatteringType'."""
        return self._calc.getRadiationType()

    def setQmax(self, qmax):
        """Set the qmax value."""
        self._calc.qmax = qmax
        self.meta["qmax"] = qmax
        return

    def getQmax(self):
        """Get the qmax value."""
        return self.meta.get('qmax')

    def setQmin(self, qmin):
        """Set the qmin value.

        This has no effect on the crystal PDF.
        
        """
        self._calc.qmin = qmin
        self.meta["qmin"] = qmin
        return

    def getQmin(self):
        """Get the qmin value."""
        return self.meta.get('qmin')

    def setPhase(self, stru = None, name = None, parset = None):
        """Add a phase to the calculated structure.

        This creates a StructureParSet or ObjCrystParSet that adapts stru to a
        ParameterSet interface. See those classes (located in
        diffpy.srfit.structure) for how they are used. The resulting
        ParameterSet will be managed by this generator.

        stru    --  diffpy.Structure.Structure, pyobjcryst.crystal.Crystal or
                    pyobjcryst.molecule.Molecule instance . Default None.
        name    --  A name to give the structure. If name is None (default),
                    then the name will be set as "phase".
        parset  --  A ParameterSet that holds the structural information. This
                    can be used to share the phase between multiple
                    PDFGenerators, and have the changes in one reflect in
                    another. If both stru and parset are specified, only parset
                    is used. Default None. 

        Raises ValueError if neither stru nor parset is specified.

        """

        if name is None:
            name = "phase"

        if stru is None and parset is None:
            raise ValueError("One of stru or parset must be specified")

        if parset is None:
            parset = struToParameterSet(name, stru)

        self._phase = parset

        # Check if the structure is a diffpy.Structure.PDFFitStructure
        # instance.
        from diffpy.Structure import Structure
        if isinstance(stru, Structure) and hasattr(stru, "pdffit"):
            self.__wrapPDFFitPars()
        else:
            self.__wrapPars()

        # Put this ParameterSet in the ProfileGenerator.
        self.addParameterSet(parset)
        return

    def __wrapPars(self):
        """Wrap the Parameters.

        This wraps the parameters provided by the PDFCalculator as SrFit
        Parameters.

        """
        parnames = ['delta1', 'delta2', 'qbroad', 'scale', 'qdamp']

        for pname in parnames:
            self.addParameter(
                ParameterAdapter(pname, self._calc, attr = pname)
                )
        return

    def __wrapPDFFitPars(self):
        """Wrap the Parameters in a pdffit-aware structure.

        This wraps the parameters provided in a pdffit-aware diffpy.Structure
        object. The DiffpyStructureAdapter (customPQConfig) looks to the
        structure for the parameter values, so we must modify them at that
        level, rather than at the PDFCalculator level.

        """
        pdfparnames = ['delta1', 'delta2', 'scale']

        for pname in pdfparnames:
            getter = dict.__getitem__
            setter = dict.__setitem__
            self.addParameter(
                ParameterAdapter(pname, self._phase.stru.pdffit, getter,
                    setter, pname)
                )

        parnames = ['qbroad', 'qdamp']
        for pname in parnames:
            self.addParameter(
                ParameterAdapter(pname, self._calc, attr = pname)
                )

        return


    def __prepare(self, r):
        """Prepare the calculator when a new r-value is passed."""
        # TODO - Should we handle non-uniform data?
        self._lastr = r
        self._calc.rstep = r[1] - r[0]
        self._calc.rmin = r[0]
        self._calc.rmax = r[-1] + 0.5*self._calc.rstep
        return

    def _validate(self):
        """Validate my state.

        This validates that the phase is not None.
        This performs ProfileGenerator validations.

        Raises AttributeError if validation fails.
        
        """
        if self._phase is None:
            raise AttributeError("_phase is None")
        ProfileGenerator._validate(self)
        return

    def _getConfig(self):
        """Get a configuration dictionary for the calculator."""
        attrs = ['rmin', 'rmax', 'rstep', 'qmin', 'qmax']
        cfg = dict((attr, self._calc._getDoubleAttr(attr)) for attr in
                attrs)

        # Get these values directly from the parameters so we don't have to
        # worry about the ultimate sources.
        parnames = ['delta1', 'delta2', 'qbroad', 'scale', 'qdamp']
        for pname in parnames:
            cfg[pname] = self.get(pname).value
        return cfg


    def __call__(self, r):
        """Calculate the PDF.

        This ProfileGenerator will be used in a fit equation that will be
        optimized to fit some data.  By the time this function is evaluated,
        the crystal has been updated by the optimizer via the ObjCrystParSet
        created in setCrystal. Thus, we need only call pdf with the internal
        structure object.

        """
        if r is not self._lastr:
            self.__prepare(r)

        if self._ncpu > 1:
            cfg = self._getConfig()
            stru = self._phase._getSrRealStructure()
            w = _pdfworker(self._calc.__class__, self._ncpu, stru, cfg)
            self._calc = w.klass(**cfg)
            self._calc.setStructure(stru)
            for y in self._pool.imap_unordered(w, range(self._ncpu)):
                self._calc._mergeParallelValue(y)
        else:
            self._calc.eval(self._phase._getSrRealStructure())

        print self._calc.delta2
        y = self._calc.getPDF()

        if numpy.isnan(y).any():
            y = numpy.zeros_like(r)
        else:
            r1 = self._calc.getRgrid()
            y = numpy.interp(r, r1, y)
        return y

class _pdfworker(object):

    def __init__(self, klass, ncpu, stru, cfg):
        self.ncpu = ncpu
        self.stru = stru
        self.klass = klass
        self.cfg = cfg
        return

    def __call__(self, cpuindex):
        _calc = self.klass(**self.cfg)
        _calc._setupParallelRun(cpuindex, self.ncpu)
        return _calc.eval(self.stru)

# End class BasePDFGenerator
