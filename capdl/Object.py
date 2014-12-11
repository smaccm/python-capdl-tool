#
# Copyright 2014, NICTA
#
# This software may be distributed and modified according to the terms of
# the BSD 2-Clause license. Note that NO WARRANTY is provided.
# See "LICENSE_BSD2.txt" for details.
#
# @TAG(NICTA_BSD)
#

"""
Definitions of kernel objects.
"""

import Cap
import math

class Object(object):
    """
    Parent of all kernel objects. This class is not expected to be instantiated.
    """
    def __init__(self, name):
        self.name = name

    def is_container(self):
        return False

class ContainerObject(Object):
    """
    Common functionality for all objects that are cap containers, in the sense
    that they may have child caps.
    """
    def __init__(self, name):
        super(ContainerObject, self).__init__(name)
        self.slots = {}

    def is_container(self):
        return True

    def print_contents(self):
        def slot_index(index):
            """
            Print a slot index in a sensible way.
            """
            if index is None:
                return ''
            elif isinstance(index, int):
                return '%s: ' % hex(index)
            else:
                assert isinstance(index, str)
                return '%s: ' % index

        return '%s {\n%s\n}' % \
            (self.name, \
             '\n'.join(map(lambda x: '%s%s' % (slot_index(x[0]), x[1]), \
                  filter(lambda y: y[1] is not None, self.slots.items()))))

    def __contains__(self, key):
        return key in self.slots

    def __delitem__(self, key):
        del self.slots[key]

    def __getitem__(self, key):
        return self.slots[key]

    def __setitem__(self, slot, cap):
        self.slots[slot] = cap

    def __iter__(self):
        return self.slots.__iter__()

class Frame(Object):
    def __init__(self, name, size=4096, paddr=0):
        super(Frame, self).__init__(name)
        self.size = size
        self.paddr = paddr

    def __repr__(self):
        # Hex does not produce porcelain output across architectures due to
        # difference between Int and Long types and tacking an L on the end in
        # such cases. We do not want a distinguishing letter at the end since
        # we have asked for a hex value
        def reliable_hex(val) :
            return hex(val).rstrip('L')
        return '%(name)s = frame (%(size)s%(maybepaddr)s)' % {
            'name':self.name,
            'size':'%s' % (str(self.size / 1024) + 'k') if self.size % (1024 * 1024) != 0 \
                else str(self.size / 1024 / 1024) + 'M',
            'maybepaddr':(', paddr: %s' % reliable_hex(self.paddr)) if self.paddr != 0 else '',
        }

class PageTable(ContainerObject):
    def __repr__(self):
        return '%s = pt' % self.name

class PageDirectory(ContainerObject):
    def __repr__(self):
        return '%s = pd' % self.name

class ASIDPool(ContainerObject):
    def __repr__(self):
        return '%s = asid_pool' % self.name

def calculate_size(cnode):
    return int(math.floor(math.log(reduce(max, cnode.slots.keys(), 4), 2)) + 1)

class CNode(ContainerObject):
    def __init__(self, name, size_bits='auto'):
        super(CNode, self).__init__(name)
        self.size_bits = size_bits

    def finalise_size(self):
        if self.size_bits == 'auto':
            # Minimum CNode size is 2 bits. Maximum size (28 bits) is not
            # checked.
            self.size_bits = calculate_size(self)

    def __repr__(self):
        if self.size_bits == 'auto':
            size_bits = calculate_size(self)
        else:
            size_bits = self.size_bits
        return '%s = cnode (%s bits)' % (self.name, size_bits)

class Endpoint(Object):
    def __repr__(self):
        return '%s = ep' % self.name

class AsyncEndpoint(Object):
    def __repr__(self):
        return '%s = aep' % self.name

class TCB(ContainerObject):
    def __init__(self, name, ipc_buffer_vaddr=0x0, ip=0x0, sp=0x0, elf=None, \
            prio=254, max_prio=254, crit=3, max_crit=3, init=None, domain=None):
        super(TCB, self).__init__(name)
        self.addr = ipc_buffer_vaddr
        self.ip = ip
        self.sp = sp
        self.elf = elf or ''
        self.prio = prio
	self.max_prio = max_prio
	self.crit = crit
	self.max_crit = max_crit
        self.init = init or []
        self.domain = domain

    def __repr__(self):
        # XXX: Assumes 32-bit pointers
        s = '%(name)s = tcb (addr: 0x%(addr)0.8x, ip: 0x%(ip)0.8x, sp: 0x%(sp)0.8x, elf: %(elf)s, prio: %(prio)s, \
		max_prio: %(max_prio)s, crit: %(crit)s, max_crit: %(max_crit)s, init: %(init)s' % self.__dict__
        if self.domain is not None:
            s += ', dom: %d' % self.domain
        s += ')'
        return s

class Untyped(Object):
    def __init__(self, name, size_bits=12):
        super(Untyped, self).__init__(name)
        self.size_bits = size_bits

    def __repr__(self):
        return '%(name)s = ut (%(size_bits)s bits)' % self.__dict__

class IOPorts(Object):
    def __init__(self, name, size=65536): # 64k size is the default in CapDL spec.
        super(IOPorts, self).__init__(name)
        self.size = size

    def __repr__(self):
        return '%(name)s = io_ports (%(size)sk ports)' % \
            {'name':self.name, \
             'size':self.size / 1024}

class IODevice(Object):
    def __init__(self, name, domainID, bus, dev, fun):
        super(IODevice, self).__init__(name)
        self.domainID = domainID
        self.bus = bus
        self.dev = dev
        self.fun = fun

    def __repr__(self):
        return '%s = io_device (domainID: %d, 0x%x:%d.%d)' % (self.name, self.domainID, self.bus, self.dev, self.fun)

class IOPageTable(ContainerObject):
    def __init__(self, name, level=1):
        super(IOPageTable, self).__init__(name)
        assert level in [1, 2, 3] # Complies with CapDL spec
        self.level = level

    def __repr__(self):
        return '%(name)s = io_pt (level: %(level)s)' % self.__dict__

class IRQ(ContainerObject):
    # In the implementation there is no such thing as an IRQ object, but it is
    # simpler to model it here as an actual object.
    def __init__(self, name, number=None):
        super(IRQ, self).__init__(name)
        self.number = number

    def set_endpoint(self, aep):
        # Allow the user to pass an object or cap.
        if isinstance(aep, Object):
            assert isinstance(aep, AsyncEndpoint)
            c = Cap.Cap(aep)
        else:
            assert isinstance(aep, Cap.Cap)
            assert isinstance(aep.referent, AsyncEndpoint)
            c = aep
        self[0] = c

    def __repr__(self):
        # Note, in CapDL this is actually represented as a 0-sized CNode.
        return '%s = irq' % self.name

class VCPU(Object):
    def __repr__(self):
        return '%s = vcpu' % self.name

class SC(Object):
    def __init__(self, name, period=0x0, deadline=0x0, exec_req=0x0, flags=0x0):
        super(SC, self).__init__(name)
        self.period = period
	self.deadline = deadline
	self.exec_req = exec_req
	self.flags = flags

    def __repr__(self):
        s = '%(name)s = sc (period: %(period)s, deadline: %(deadline)s, exec_req: %(exec_req)s, flags: %(flags)s)' % self.__dict__
        return s

