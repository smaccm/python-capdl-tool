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
Various internal utility functions. Pay no mind to this file.
"""

import os

# Size of a frame and page (applies to all architectures)
FRAME_SIZE = 4096 # bytes
PAGE_SIZE = 4096 # bytes

# ARM objects, hypervisor mode doubles the section size.
ARM_LARGE_PAGE_SIZE = 64 * 1024           #64K
if os.environ.get('ARM_HYP', '') == '1':
    ARM_SECTION_SIZE = 2 * 1024 * 1024            #1M
    ARM_SUPER_SECTION_SIZE = 2 * 16 * 1024 * 1024 #16M
else:
    ARM_SECTION_SIZE = 1024 * 1024            #1M
    ARM_SUPER_SECTION_SIZE = 16 * 1024 * 1024 #16M

# IA32 objects
IA32_4M_PAGE_SIZE = 4 * 1024 * 1024       #4M

# X86_64 objects(unsupported)
X64_2M_PAGE_SIZE = 2 * 1024 * 1024        #2M

def round_down(n, alignment=FRAME_SIZE):
    """
    Round a number down to 'alignment'.
    """
    return n / alignment * alignment

def page_table_coverage(arch):
    """
    The number of bytes a page table covers.
    """
    if arch.lower() in ['x86', 'ia32']:
        # On IA32 a page table covers 4M
        return 4 * 1024 * 1024
    elif arch.lower() in ['arm', 'arm11']:
        # On ARM a page table usually covers 1M,
        # ARM hypervisor mode covers 2M
        if os.environ.get('ARM_HYP', '') == '1':
            return 2 * 1024 * 1024
        else:
            return 1 * 1024 * 1024
    else:
        # NB: If you end up in this branch while dealing with an ELF that you
        # are reasonably sure is ARM, chances are you don't have a recent
        # enough version of pyelftools. ARM support was only added recently.
        raise NotImplementedError

def page_table_vaddr(arch, vaddr):
    """
    The base virtual address of a page table, derived from the virtual address
    of a location within that table's coverage.
    """
    return round_down(vaddr, page_table_coverage(arch))

def page_table_index(arch, vaddr):
    """
    The index of a page table within a containing page directory, derived from
    the virtual address of a location within that table's coverage.
    """
    return vaddr / page_table_coverage(arch)

def page_index(arch, vaddr):
    """
    The index of a page within a containing page table, derived from the
    virtual address of a location within that page.
    """
    return vaddr % page_table_coverage(arch) / PAGE_SIZE

def page_vaddr(vaddr):
    """
    The base virtual address of a page, derived from the virtual address of a
    location within that page.
    """
    return vaddr / PAGE_SIZE * PAGE_SIZE
