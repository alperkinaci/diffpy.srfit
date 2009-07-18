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
"""Swapper visitor for replacing literals in an equation with other literals.

"""

from .visitor import Visitor

from .. import Clicker

class Swapper(Visitor):
    """Swapper for swapping out one literal for another in a literal tree.

    Note that this cannot swap out a root node of a literal tree.

    Attributes:
    newlit  --  The literal to be placed into the literal tree. See the class
                for how the replacement takes place.
    oldlit  --  The literal to be replaced.
    _swap   --  A flag indicating to replace a child node.

    """

    def __init__(self, oldlit, newlit):
        """Initialize.

        oldlit  --  The literal to be replaced.
        newlit  --  The literal to be placed into the literal tree. See the
                    class for how the replacement takes place.

        Raises TypeError if the new literal does not have an interface that is
        compatible with the old one.

        """

        for attrname in dir(oldlit):
            if not hasattr(newlit, attrname):
                raise TypeError("New and old Literal are not compatible")

        self.newlit = newlit
        self.oldlit = oldlit

        self._swap = False

        return

    def onArgument(self, arg):
        """Process an Argument node.

        Tell the parent to swap the old Argument with the new one. 

        """

        if arg is self.oldlit:

            self._swap = True

            self.newlit.clicker.click()

        return

    def onOperator(self, op):
        """Process an Operator node.

        The visitor does pass through an Operator.

        Put the children of the old Operator in the new Operator. Tell the
        parent to swap this operator out. This does not detach the children
        from the old Operator.
        
        """

        for literal in op.args:
            literal.identify(self)

        # If we've been told to swap out a child, then we must do it in-place.
        if self._swap:

            idx = op.args.index(self.oldlit)
            op.args[idx] = self.newlit
            op.clicker.addSubject(self.newlit.clicker)

            self.newlit.clicker.click()
            self._swap = False

        # If this is the old literal, then we want to place it's children into
        # the new literal.
        if op is self.oldlit:

            self._swap = True

            for literal in op.args:
                self.newlit.addLiteral(literal)



        return

    def onPartition(self, part):
        """Process a Partition node.

        The visitor does pass through a Partition.

        Tell the parent to swap this Partition for the new one.  We assume that
        the new Partition already has Arguments, so the Arguments of an old
        Partition will not be transferred to a new one.
        
        """

        for literal in part.args:
            literal.identify(self)

        # Swap out a child
        if self._swap:
            idx = part.args.index(self.oldlit)
            part.args[idx] = self.newlit
            part.clicker.addSubject(self.newlit.clicker)

            self.newlit.clicker.click()
            self._swap = False

        # Swap out children in the new operator
        if part is self.oldlit:

            self._swap = True

            self.newlit.clicker.click()

        return


    def onGenerator(self, gen):
        """Process a Generator node.

        The visitor does not pass through a Generator.
        
        Tell the parent to swap this Generator for the new one.  We assume that
        the new Generator already has assigned Literals, so the Literals of the
        old Generator will not be transferred to a new one.

        """

        # Swap out children in the new generator
        if gen is self.oldlit:

            self._swap = True

            self.newlit.clicker.click()

        return


# version
__id__ = "$Id$"

#
# End of file