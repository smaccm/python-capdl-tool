#!/usr/bin/env python
#
# Copyright 2014, NICTA
#
# This software may be distributed and modified according to the terms of
# the BSD 2-Clause license. Note that NO WARRANTY is provided.
# See "LICENSE_BSD2.txt" for details.
#
# @TAG(NICTA_BSD)
#

import capdl

a = capdl.TCB('foo')
b = capdl.TCB('bar')

spec1 = capdl.Spec()
spec2 = capdl.Spec()
spec1.merge(spec2)
assert len(spec1.objs) == 0

spec1 = capdl.Spec()
spec1.add_object(a)
spec2 = capdl.Spec()
spec1.merge(spec2)
assert spec1.objs == set([a])

spec1 = capdl.Spec()
spec1.add_object(a)
spec2 = capdl.Spec()
spec2.add_object(b)
spec1.merge(spec2)
assert spec1.objs == set([a, b])
