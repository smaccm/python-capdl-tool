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
Functionality related to handling ELF file input. This is the only section of
this module that relies on elftools, so it is possible to use this module
without elftools installed by not importing this particular file.
"""
from elftools.elf.elffile import ELFFile
from elftools.elf.constants import P_FLAGS
from Object import TCB
from util import *
from PageCollection import PageCollection
import re

class ELF(object):
    def __init__(self, elf, name=''):
        """
        This constructor is overloaded and can accept either a string as the
        parameter 'elf', or a stream to ELF data. 'name' is only used when
        generating CapDL from the ELF file.
        """
        if isinstance(elf, str):
            f = open(elf, 'rb')
        else:
            f = elf
        self._elf = ELFFile(f)
        self.name = name
        self.symtab = {}
        self._symtab_src = None

    def get_entry_point(self):
        return self._elf['e_entry']

    def _get_symbol(self, symbol):
        if symbol in self.symtab:
            return self.symtab[symbol]

        if self._symtab_src is None:
            table = self._elf.get_section_by_name('.symtab')
            if not table:
                # This ELF file has been stripped.
                raise Exception('No symbol table available')
            self._symtab_src = table.iter_symbols()

        for s in self._symtab_src:
            self.symtab[s.name] = s
            if s.name == symbol:
                return s
        self._symtab_src = None
        return None

    def get_symbol_vaddr(self, symbol):
        sym = self._get_symbol(symbol)
        if sym:
            return sym['st_value']
        return None

    def get_symbol_size(self, symbol):
        sym = self._get_symbol(symbol)
        if sym:
            return sym['st_size']
        return None

    def _safe_name(self):
        """
        Replace characters that the CapDL tools parse differently.
        """
        return re.sub(r'[^A-Za-z0-9]', '_', self.name)

    def get_pages_with_section(self, infer_asid=True, pd=None):
        """
        """
        TYPE = {"ignore": 1, "shared": 2, "persistent": 3, "guarded": 4}
        regex = re.compile("^[ignore_ shared_ persistent_ guarded]", re.I);
        sections = filter(lambda x: regex.match(x.name), self._elf.iter_sections())

        pages = PageCollection(self._safe_name(), self.get_arch(), infer_asid, pd)
        for seg in self._elf.iter_segments():
            if not seg['p_type'] == 'PT_LOAD':
                continue
            if seg['p_memsz'] == 0:
                continue

            regions = [{'addr': seg['p_vaddr'], 'size': seg['p_memsz'], 'type': 0}]
            sects = filter(seg.section_in_segment, sections)
            for sec in sects:
                region = [x for x in regions if sec['sh_addr'] in range(x['addr'], x['addr'] + x['size'])]
                assert(len(region) == 1)
                region = region[0]
                orig_size = region['size']
                region['size'] = sec['sh_addr'] - region['addr']
                regions += [{'addr': sec['sh_addr'], 'size': sec['sh_size'], \
                        'type': TYPE[sec.name.split('_')[0]]}, \
                        {'addr': sec['sh_addr'] + sec['sh_size'], \
                        'size': orig_size - region['size'] - sec['sh_size'], 'type': 0}]
            regions = [x for x in regions if x['size'] != 0]

            # Allocate pages
            for reg in regions:
                if reg['type'] == 1:
                    pages.add_page(reg['addr'], \
                        (seg['p_flags'] & P_FLAGS.PF_R) > 0, \
                        (seg['p_flags'] & P_FLAGS.PF_W) > 0, \
                        (seg['p_flags'] & P_FLAGS.PF_X) > 0, reg['size'])
                elif reg['type'] in [2, 3, 4]:
                    vaddr = round_down(reg['addr'])
                    while vaddr < reg['addr'] + reg['size']:
                        pages.add_page(vaddr, \
                            (seg['p_flags'] & P_FLAGS.PF_R) > 0, \
                            (seg['p_flags'] & P_FLAGS.PF_W) > 0, \
                            (seg['p_flags'] & P_FLAGS.PF_X) > 0)
                        vaddr += PAGE_SIZE
                else:
                    vaddr = round_down(reg['addr'])
                    remain = reg['size']
                    while vaddr < reg['addr'] + reg['size']:
                        size = PAGE_SIZE
                        if self.get_arch().lower() in ['x86', 'ia32']:
                            if remain >= IA32_4M_PAGE_SIZE and vaddr % IA32_4M_PAGE_SIZE == 0:
                                size = IA32_4M_PAGE_SIZE
                        elif self.get_arch().lower() in ['arm', 'arm11']:
                            if remain >= ARM_SUPER_SECTION_SIZE and vaddr % ARM_SUPER_SECTION_SIZE == 0:
                                size = ARM_SUPER_SECTION_SIZE
                            elif remain >= ARM_SECTION_SIZE and vaddr % ARM_SECTION_SIZE == 0:
                                size = ARM_SECTION_SIZE
                            elif remain >= ARM_SECTION_SIZE and vaddr % ARM_LARGE_PAGE_SIZE == 0:
                                size = ARM_LARGE_PAGE_SIZE
                        else:
                            raise NotImplementedError

                        pages.add_page(vaddr, \
                            (seg['p_flags'] & P_FLAGS.PF_R) > 0, \
                            (seg['p_flags'] & P_FLAGS.PF_W) > 0, \
                            (seg['p_flags'] & P_FLAGS.PF_X) > 0, size)
                        vaddr += size
                        remain -= size
        return pages

    def get_arch(self):
        return self._elf.get_machine_arch()

    def get_pages(self, infer_asid=True, pd=None):
        """
        Returns a dictionary of pages keyed on base virtual address, that are
        required to ELF load this file. Each dictionary entry is a dictionary
        containing booleans 'read', 'write' and 'execute' for the permissions
        of the page.
        """
        pages = PageCollection(self._safe_name(), self.get_arch(), infer_asid, pd)
        for seg in self._elf.iter_segments():
            if not seg['p_type'] == 'PT_LOAD':
                continue
            if seg['p_memsz'] == 0:
                continue
            vaddr = round_down(int(seg['p_vaddr']))
            r = (seg['p_flags'] & P_FLAGS.PF_R) > 0
            w = (seg['p_flags'] & P_FLAGS.PF_W) > 0
            x = (seg['p_flags'] & P_FLAGS.PF_X) > 0
            map(lambda y: pages.add_page(y, r, w, x),
                xrange(vaddr, int(seg['p_vaddr']) + int(seg['p_memsz']),
                    PAGE_SIZE))
        return pages

    def get_spec(self, infer_tcb=True, infer_asid=True, pd=None, special_sections=False):
        """
        Return a CapDL spec with as much information as can be derived from the
        ELF file in isolation.
        """
        if special_sections == True:
            pages = self.get_pages_with_section(infer_asid, pd)
        else:
            pages = self.get_pages(infer_asid, pd)
        spec = pages.get_spec()

        if infer_tcb:
            # Create a single TCB.
            tcb = TCB('tcb_%s' % self._safe_name(), ip=self.get_entry_point(), \
                elf=self.name)
            spec.add_object(tcb)
            tcb['vspace'] = pages.get_page_directory()[1]

        return spec

    def __repr__(self):
        return str(self._elf)
