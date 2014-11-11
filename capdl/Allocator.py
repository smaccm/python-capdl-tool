#
# Copyright 2014, NICTA
#
# This software may be distributed and modified according to the terms of
# the BSD 2-Clause license. Note that NO WARRANTY is provided.
# See "LICENSE_BSD2.txt" for details.
#
# @TAG(NICTA_BSD)
#

from Object import Frame, PageTable, PageDirectory, CNode, Endpoint, \
    AsyncEndpoint, TCB, Untyped, IOPageTable, Object, IRQ, IOPorts, IODevice, \
    VCPU, ASIDPool
from Spec import Spec
from Cap import Cap

import os;

seL4_UntypedObject = 0
seL4_TCBObject = 1
seL4_EndpointObject = 2
seL4_AsyncEndpointObject = 3
seL4_CapTableObject = 4

seL4_ARM_SmallPageObject = 5
seL4_ARM_LargePageObject = 6
seL4_ARM_SectionObject = 7
seL4_ARM_SuperSectionObject = 8
seL4_ARM_PageTableObject = 9
seL4_ARM_PageDirectoryObject = 10

seL4_IA32_4K = 15
seL4_IA32_4M = 16
seL4_IA32_PageTableObject = 17
seL4_IA32_PageDirectoryObject = 18
seL4_IA32_IOPageTableObject = 19
seL4_IA32_IOPort = 20
seL4_IA32_IOSpace = 21
seL4_IA32_VCPU = 22

seL4_FrameObject = 25
seL4_IRQControl = 26

seL4_PageDirectoryObject = 30
seL4_ASID_Pool = 31

seL4_CanRead = 1
seL4_CanWrite = 2
seL4_CanGrant = 4
seL4_AllRights = seL4_CanRead|seL4_CanWrite|seL4_CanGrant

class ObjectAllocator(object):
    '''
    An offline object allocator. This can be useful for incrementally
    generating a CapDL spec.
    '''

    def __init__(self, prefix='obj'):
        self.prefix = prefix
        self.counter = 0
        self.spec = Spec()
        self.labels = {}
        self.name_to_object = {}

    def _assign_label(self, label, obj):
        if label not in self.labels:
            self.labels[label] = set()
        self.labels[label].add(obj)

    def relabel(self, label, obj):
        for l in self.labels:
            if obj in self.labels[l]:
                self.labels[l].remove(obj)
                break
        self._assign_label(label, obj)

    def alloc(self, type, name=None, label=None, **kwargs):
        if name is None:
            name = '%s%d' % (self.prefix, self.counter)

        o = self.name_to_object.get(name)
        if not o is None:
            assert o in self.labels.get(label, set()), \
                'attempt to allocate object %s under a new, differing label' % o.name
            return o

        self.counter += 1
        if type == seL4_UntypedObject:
            size_bits = kwargs.get('size_bits', 12)
            o = Untyped(name, size_bits)
        elif type == seL4_TCBObject:
            o = TCB(name)
        elif type == seL4_EndpointObject:
            o = Endpoint(name)
        elif type == seL4_AsyncEndpointObject:
            o = AsyncEndpoint(name)
        elif type == seL4_CapTableObject:
            o = CNode(name, **kwargs)
        elif type == seL4_FrameObject:
            o = Frame(name, 4096, **kwargs)
        elif type == seL4_IA32_4K or type == seL4_ARM_SmallPageObject:
            o = Frame(name, 4096, **kwargs) # 4K
        elif type == seL4_ARM_LargePageObject:
            o = Frame(name, 64 * 1024, **kwargs) # 64K
        elif type == seL4_ARM_SectionObject:
            if os.environ.get('ARM_HYP', '') == '1':
                o = Frame(name, 1024 * 1024 * 2, **kwargs) # 2M
            else:
                o = Frame(name, 1024 * 1024, **kwargs) # 1M
        elif type == seL4_ARM_SuperSectionObject:
            if os.environ.get('ARM_HYP', '') == '1':
                o = Frame(name, 32 * 1024 * 1024, **kwargs) # 32M
            else:
                o = Frame(name, 16 * 1024 * 1024, **kwargs) # 16M
        elif type == seL4_IA32_PageTableObject or type == seL4_ARM_PageTableObject:
            o = PageTable(name)
        elif type in [seL4_IA32_PageDirectoryObject,
                      seL4_ARM_PageDirectoryObject,
                      seL4_PageDirectoryObject]:
            o = PageDirectory(name)
        elif type == seL4_IA32_4M:
            o = Frame(name, 4096 * 1024, **kwargs) # 4M
        elif type == seL4_IA32_IOPageTableObject:
            o = IOPageTable(name)
        elif type == seL4_IA32_IOPort:
            # There is only one IOPort object in the system, which describes the entire
            # port region.
            for o in self:
                if isinstance(o, IOPorts):
                    return o
            o = IOPorts(name)
        elif type == seL4_IA32_IOSpace:
            o = IODevice(name, **kwargs)
        elif type == seL4_IA32_VCPU:
            o = VCPU(name)
        elif type == seL4_IRQControl:
            if 'number' in kwargs and 'aep' in kwargs:
                o = IRQ(name, kwargs['number'])
                o.set_endpoint(kwargs['aep'])
            else:
                raise ValueError
        elif type == seL4_ASID_Pool:
            o = ASIDPool(name)
        else:
            raise Exception('Invalid object type %s' % type)
        self.spec.add_object(o)
        self.name_to_object.update({name:o})
        self._assign_label(label, o)
        return o

    def merge(self, spec, label=None):
        assert isinstance(spec, Spec)
        self.spec.merge(spec)
        [self._assign_label(label, x) for x in spec.objs]
        [self.name_to_object.update({x.name:x}) for x in spec]

    def __getitem__(self, key):
        return self.spec[key]

    def __iter__(self):
        return self.spec.__iter__()

class CSpaceAllocator(object):
    '''
    An offline CSpace allocator. Note that this is only capable of allocating
    from a single level CSpace.
    '''

    def __init__(self, cnode):
        assert isinstance(cnode, CNode)
        self.cnode = cnode
        self.objname_to_slot = {}
        self.slot = 1 # Skip the null slot

    def alloc(self, obj, **kwargs):
        '''
        Allocate a cap in the next available slot, referencing the given
        object. The caller is expected to pass either (a) no extra parameters
        indicating a cap with no rights, (b) the extra parameter 'rights' set
        to one of 0/seL4_CanRead/seL4_CanWrite/seL4_CanGrant/seL4_AllRights,
        or (c) some combination of the boolean parameters 'read', 'write' and
        'grant' indicating the rights of the cap.
        '''
        assert isinstance(obj, Object) or obj is None

        # Check if the object exists already
        # IOPort is a special case of which the object name is not unique.
        if not obj is None and not isinstance(obj, IOPorts):
            slot = self.objname_to_slot.get(obj.name)
            if not slot is None:
                return slot

        while self.slot in self.cnode.slots:
            # Skip slots the caller may have manually populated.
            self.slot += 1
        if self.cnode.size_bits != 'auto' and self.slot > (1 << self.cnode.size_bits) - 1:
            # Ran out of space in the CNode.
            return -1
        slot = self.slot
        self.slot += 1
        if obj is None:
            # The caller requested just a free slot.
            cap = None
        else:
            if 'rights' in kwargs:
                assert 'read' not in kwargs
                assert 'write' not in kwargs
                assert 'grant' not in kwargs
                read = kwargs['rights'] & seL4_CanRead > 0
                write = kwargs['rights'] & seL4_CanWrite > 0
                grant = kwargs['rights'] & seL4_CanGrant > 0
            else:
                read = kwargs.get('read', False)
                write = kwargs.get('write', False)
                grant = kwargs.get('grant', False)
            cap = Cap(obj, read=read, write=write, grant=grant)
        self.cnode[slot] = cap
        if not obj is None:
            self.objname_to_slot.update({obj.name: slot})
        return slot
