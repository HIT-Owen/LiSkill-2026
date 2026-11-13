"""License clause corpus used by the released demo.

Each entry keeps a *clause-level* excerpt of the license instead of its full
legal text.  The excerpts are contiguous sentences taken from the licenses
themselves and are sufficient for the term–attitude reader: the paper's pipeline
segments the full text into sentences anyway (NLTK, §3.3.2), and the demo keeps
the sentences that carry normative content.

The demo ships 22 standard licenses plus 3 representative custom texts.  The
full 708-license SPDX / OSI / tldrLegal / FOSSology reference set is produced by
`liskill collect reference` from sources that are not redistributed here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class LegalText:
    license_id: str
    full_name: str
    clauses: List[str]
    aliases: List[str] = field(default_factory=list)
    version: str = ""
    osi_approved: bool = True
    deprecated: bool = False

    @property
    def text(self) -> str:
        return "\n".join(self.clauses)


MIT_GRANT = (
    "Permission is hereby granted, free of charge, to any person obtaining a copy of "
    "this software and associated documentation files, to deal in the Software without "
    "restriction, including without limitation the rights to use, copy, modify, merge, "
    "publish, distribute, sublicense, and/or sell copies of the Software."
)
AS_IS = (
    "THE SOFTWARE IS PROVIDED AS IS, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, "
    "INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY."
)
NO_LIABILITY = (
    "In no event shall the authors or copyright holders be liable for any claim, damages "
    "or other liability, whether in an action of contract, tort or otherwise, arising from "
    "the use of the Software."
)

LICENSE_TEXTS: Dict[str, LegalText] = {
    # ------------------------------------------------------------------ permissive
    "MIT": LegalText(
        "MIT", "MIT License",
        [
            MIT_GRANT,
            "The above copyright notice and this permission notice shall be included in "
            "all copies or substantial portions of the Software.",
            AS_IS,
            NO_LIABILITY,
        ],
        aliases=["MIT License", "Expat", "MIT/X11"],
    ),
    "MIT-0": LegalText(
        "MIT-0", "MIT No Attribution",
        [
            MIT_GRANT,
            AS_IS,
            NO_LIABILITY,
        ],
        aliases=["MIT No Attribution", "MIT-0 License"],
    ),
    "Apache-2.0": LegalText(
        "Apache-2.0", "Apache License 2.0",
        [
            "Subject to the terms and conditions of this License, each Contributor hereby "
            "grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free, "
            "irrevocable copyright license to reproduce, prepare Derivative Works of, "
            "publicly display, publicly perform, sublicense, and distribute the Work and "
            "such Derivative Works in Source or Object form.",
            "You must give any other recipients of the Work or Derivative Works a copy of "
            "this License.",
            "You must cause any modified files to carry prominent notices stating that You "
            "changed the files.",
            "You must retain, in the Source form of any Derivative Works that You "
            "distribute, all copyright, patent, trademark, and attribution notices from the "
            "Source form of the Work.",
            "If the Work includes a NOTICE text file, then You must include a readable copy "
            "of the attribution notices contained within such NOTICE file.",
            "You may add Your own copyright statement to Your modifications and may provide "
            "additional or different license terms and conditions for use, reproduction, or "
            "distribution of Your modifications.",
            "Each Contributor hereby grants to You a perpetual, worldwide, non-exclusive, "
            "no-charge, royalty-free, irrevocable patent license to make, have made, use, "
            "offer to sell, sell, import, and otherwise transfer the Work.",
            "This License does not grant permission to use the trade names, trademarks, "
            "service marks, or product names of the Licensor.",
            "Unless required by applicable law or agreed to in writing, Licensor provides "
            "the Work on an AS IS BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, "
            "either express or implied.",
            "In no event and under no legal theory shall any Contributor be liable to You "
            "for damages, including any direct or consequential damages.",
        ],
        aliases=["Apache 2.0", "Apache License, Version 2.0", "Apache-2", "ASL 2.0"],
        version="2.0",
    ),
    "BSD-2-Clause": LegalText(
        "BSD-2-Clause", "BSD 2-Clause Simplified License",
        [
            "Redistribution and use in source and binary forms, with or without "
            "modification, are permitted provided that the following conditions are met.",
            "Redistributions of source code must retain the above copyright notice, this "
            "list of conditions and the following disclaimer.",
            "Redistributions in binary form must reproduce the above copyright notice, this "
            "list of conditions and the following disclaimer in the documentation.",
            AS_IS,
            NO_LIABILITY,
        ],
        aliases=["BSD 2-Clause", "Simplified BSD", "FreeBSD License"],
    ),
    "BSD-3-Clause": LegalText(
        "BSD-3-Clause", "BSD 3-Clause New or Revised License",
        [
            "Redistribution and use in source and binary forms, with or without "
            "modification, are permitted provided that the following conditions are met.",
            "Redistributions of source code must retain the above copyright notice, this "
            "list of conditions and the following disclaimer.",
            "Redistributions in binary form must reproduce the above copyright notice, this "
            "list of conditions and the following disclaimer in the documentation.",
            "Neither the name of the copyright holder nor the names of its contributors may "
            "be used to endorse or promote products derived from this software without "
            "specific prior written permission.",
            AS_IS,
            NO_LIABILITY,
        ],
        aliases=["BSD 3-Clause", "New BSD", "Modified BSD", "BSD-3"],
    ),
    "ISC": LegalText(
        "ISC", "ISC License",
        [
            "Permission to use, copy, modify, and distribute this software for any purpose "
            "with or without fee is hereby granted, provided that the above copyright notice "
            "and this permission notice appear in all copies.",
            AS_IS,
            NO_LIABILITY,
        ],
        aliases=["ISC License", "OpenBSD License"],
    ),
    "Zlib": LegalText(
        "Zlib", "zlib License",
        [
            "This software is provided as-is, without any express or implied warranty.",
            "Permission is granted to anyone to use this software for any purpose, "
            "including commercial applications, and to alter it and redistribute it freely.",
            "The origin of this software must not be misrepresented and altered source "
            "versions must be plainly marked as such.",
        ],
        aliases=["zlib License", "zlib/libpng"],
    ),
    "Unlicense": LegalText(
        "Unlicense", "The Unlicense",
        [
            "This is free and unencumbered software released into the public domain.",
            "Anyone is free to copy, modify, publish, use, compile, sell, or distribute this "
            "software, either in source code form or as a compiled binary, for any purpose, "
            "commercial or non-commercial, and by any means.",
            "In no event shall the authors be liable for any claim, damages or other "
            "liability arising from the use of the software.",
        ],
        aliases=["The Unlicense", "UNLICENSE"],
        osi_approved=True,
    ),
    "CC0-1.0": LegalText(
        "CC0-1.0", "Creative Commons Zero v1.0 Universal",
        [
            "The person who associated a work with this deed has dedicated the work to the "
            "public domain by waiving all of his or her rights to the work worldwide.",
            "You can copy, modify, distribute and perform the work, even for commercial "
            "purposes, all without asking permission.",
            "The work is provided as-is, without warranties of any kind.",
        ],
        aliases=["CC0", "CC Zero", "Creative Commons Zero"],
        version="1.0",
    ),
    # ------------------------------------------------------------- creative commons
    "CC-BY-4.0": LegalText(
        "CC-BY-4.0", "Creative Commons Attribution 4.0 International",
        [
            "You are free to share, copy and redistribute the material in any medium or "
            "format, and to adapt, remix, transform, and build upon the material for any "
            "purpose, even commercially.",
            "You must give appropriate credit, provide a link to the license, and indicate "
            "if changes were made.",
            "No warranties are given.",
        ],
        aliases=["CC BY 4.0", "CC-BY", "Creative Commons Attribution 4.0"],
        version="4.0",
    ),
    "CC-BY-SA-4.0": LegalText(
        "CC-BY-SA-4.0", "Creative Commons Attribution ShareAlike 4.0 International",
        [
            "You are free to share, copy and redistribute the material in any medium or "
            "format, and to adapt, remix, transform, and build upon the material for any "
            "purpose, even commercially.",
            "You must give appropriate credit, provide a link to the license, and indicate "
            "if changes were made.",
            "If you remix, transform, or build upon the material, you must distribute your "
            "contributions under the same license as the original.",
            "No warranties are given.",
        ],
        aliases=["CC BY-SA 4.0", "CC-BY-SA", "Creative Commons Attribution ShareAlike 4.0"],
        version="4.0",
    ),
    "CC-BY-NC-4.0": LegalText(
        "CC-BY-NC-4.0", "Creative Commons Attribution NonCommercial 4.0 International",
        [
            "You are free to share, copy and redistribute the material in any medium or "
            "format, and to adapt, remix, transform, and build upon the material.",
            "You must give appropriate credit, provide a link to the license, and indicate "
            "if changes were made.",
            "You may not use the material for commercial purposes.",
            "No warranties are given.",
        ],
        aliases=["CC BY-NC 4.0", "CC-BY-NC", "Creative Commons Attribution NonCommercial 4.0"],
        version="4.0",
    ),
    "CC-BY-NC-SA-4.0": LegalText(
        "CC-BY-NC-SA-4.0",
        "Creative Commons Attribution NonCommercial ShareAlike 4.0 International",
        [
            "You are free to share, copy and redistribute the material in any medium or "
            "format, and to adapt, remix, transform, and build upon the material.",
            "You may not use the material for commercial purposes.",
            "If you remix, transform, or build upon the material, you must distribute your "
            "contributions under the same license as the original.",
        ],
        aliases=["CC BY-NC-SA 4.0", "CC-BY-NC-SA"],
        version="4.0",
    ),
    # -------------------------------------------------------------------- copyleft
    "GPL-2.0-only": LegalText(
        "GPL-2.0-only", "GNU General Public License v2.0 only",
        [
            "You may copy and distribute verbatim copies of the Program's source code as you "
            "receive it, in any medium, provided that you conspicuously and appropriately "
            "publish on each copy an appropriate copyright notice and disclaimer of warranty.",
            "You may modify your copy or copies of the Program and copy and distribute such "
            "modifications, provided that you also meet all of these conditions.",
            "You must cause the modified files to carry prominent notices stating that you "
            "changed the files and the date of any change.",
            "You must cause any work that you distribute or publish, that in whole or in "
            "part contains or is derived from the Program, to be licensed as a whole at no "
            "charge to all third parties under the terms of this License.",
            "You may not impose any further restrictions on the recipients' exercise of the "
            "rights granted herein.",
            "You may charge a fee for the physical act of transferring a copy.",
            "This program is distributed in the hope that it will be useful, but WITHOUT ANY "
            "WARRANTY; without even the implied warranty of MERCHANTABILITY.",
            "In no event unless required by applicable law will any copyright holder be "
            "liable to you for damages.",
        ],
        aliases=["GPLv2", "GPL 2.0", "GPL-2.0", "GNU GPL v2"],
        version="2.0",
    ),
    "GPL-3.0-only": LegalText(
        "GPL-3.0-only", "GNU General Public License v3.0 only",
        [
            "You may convey verbatim copies of the Program's source code as you receive it, "
            "in any medium, provided that you conspicuously and appropriately publish on "
            "each copy an appropriate copyright notice and a disclaimer of warranty.",
            "You may convey a work based on the Program, or the modifications to produce it "
            "from the Program, in the form of source code, provided that you also meet all "
            "of these conditions.",
            "You must license the entire work, as a whole, under this License to anyone who "
            "comes into possession of a copy.",
            "Therefore, you must also offer the Corresponding Source to anyone who receives "
            "the work.",
            "You may not impose any further restrictions on the exercise of the rights "
            "granted under this License.",
            "Sublicensing is not allowed.",
            "Each contributor grants you a non-exclusive, worldwide, royalty-free patent "
            "license to make, use, sell, offer for sale, import and otherwise run, modify "
            "and propagate the contents of its contributor version.",
            "Notwithstanding any other provision of this License, you may not propagate or "
            "convey a covered work except as expressly permitted under this License.",
            "THERE IS NO WARRANTY FOR THE PROGRAM, TO THE EXTENT PERMITTED BY APPLICABLE "
            "LAW.",
            "In no event will any copyright holder be liable to you for damages, including "
            "any general or consequential damages arising out of the use of the program.",
        ],
        aliases=["GPLv3", "GPL 3.0", "GPL-3.0", "GNU GPL v3"],
        version="3.0",
    ),
    "AGPL-3.0-only": LegalText(
        "AGPL-3.0-only", "GNU Affero General Public License v3.0 only",
        [
            "You may convey verbatim copies of the Program's source code as you receive it, "
            "in any medium, provided that you conspicuously and appropriately publish on "
            "each copy an appropriate copyright notice.",
            "You must license the entire work, as a whole, under this License to anyone who "
            "comes into possession of a copy.",
            "Therefore, you must also offer the Corresponding Source to anyone who receives "
            "the work.",
            "If you modify the Program, your modified version must prominently offer all "
            "users interacting with it remotely through a computer network an opportunity "
            "to receive the Corresponding Source of your version.",
            "You may not impose any further restrictions on the exercise of the rights "
            "granted under this License.",
            "Sublicensing is not allowed.",
            "Each contributor grants you a non-exclusive, worldwide, royalty-free patent "
            "license to make, use, sell, offer for sale, import and otherwise run, modify "
            "and propagate the contents of its contributor version.",
            "THERE IS NO WARRANTY FOR THE PROGRAM, TO THE EXTENT PERMITTED BY APPLICABLE "
            "LAW.",
            "In no event will any copyright holder be liable to you for damages.",
        ],
        aliases=["AGPLv3", "AGPL 3.0", "AGPL-3.0", "GNU AGPL v3"],
        version="3.0",
    ),
    "LGPL-2.1-only": LegalText(
        "LGPL-2.1-only", "GNU Lesser General Public License v2.1 only",
        [
            "You may copy and distribute verbatim copies of the Library's complete source "
            "code as you receive it, in any medium, provided that you conspicuously and "
            "appropriately publish on each copy an appropriate copyright notice.",
            "You may modify your copy or copies of the Library, provided that you also meet "
            "all of these conditions.",
            "You must include a copy of this License with each copy of the Library.",
            "If you distribute the Library in object code form, you must also make the "
            "source code available to the recipient.",
            "You may not impose any further restrictions on the recipients' exercise of the "
            "rights granted herein.",
            "THERE IS NO WARRANTY FOR THE LIBRARY.",
            "In no event will any copyright holder be liable to you for damages.",
        ],
        aliases=["LGPLv2.1", "LGPL 2.1", "LGPL-2.1", "GNU LGPL v2.1"],
        version="2.1",
    ),
    "MPL-2.0": LegalText(
        "MPL-2.0", "Mozilla Public License 2.0",
        [
            "You may use, reproduce, make available, modify, display, perform, distribute "
            "and otherwise exploit the Covered Software, with or without modifications, "
            "provided that you comply with the conditions of this License.",
            "If You distribute Covered Software in Executable Form, then You must also make "
            "the Source Code Form available to the recipients.",
            "You must inform recipients that the Source Code Form of the Covered Software is "
            "governed by the terms of this License, and how they can obtain a copy of this "
            "License.",
            "You may distribute the Executable Form or sublicense it under different "
            "terms.",
            "The Covered Software is provided under this License on an as-is basis, without "
            "warranty of any kind.",
        ],
        aliases=["MPL 2.0", "MPL2", "Mozilla Public License, v. 2.0"],
        version="2.0",
    ),
    # ------------------------------------------------------------ source available
    "Elastic-2.0": LegalText(
        "Elastic-2.0", "Elastic License 2.0",
        [
            "You may use, copy, distribute, make available, and prepare derivative works of "
            "the software for your own internal business purposes.",
            "You may not provide the software to others as a managed service or as a hosted "
            "service.",
            "You may not move, copy, or reuse any portion of the functionality of the "
            "software in a competing product or service.",
            "You may not reverse engineer, decompile, or disassemble the software.",
        ],
        aliases=["Elastic License 2.0", "ELv2", "Elastic License"],
        version="2.0",
        osi_approved=False,
    ),
    "BUSL-1.1": LegalText(
        "BUSL-1.1", "Business Source License 1.1",
        [
            "Licensor hereby grants you a non-exclusive, non-transferable, worldwide, "
            "royalty-free, limited license to use, copy, modify, and distribute the Licensed "
            "Work for non-production use only.",
            "You may not use the Licensed Work for a commercial production use.",
        ],
        aliases=["Business Source License", "BUSL", "BSL 1.1"],
        version="1.1",
        osi_approved=False,
    ),
    "SSPL-1.0": LegalText(
        "SSPL-1.0", "Server Side Public License v1",
        [
            "You may copy, modify, and distribute the Program subject to the terms of this "
            "License.",
            "If you make the functionality of the Program available to third parties as a "
            "service, you must make the Service Source Code available via a network "
            "download.",
            "You must license the entire work under this License.",
            "THERE IS NO WARRANTY FOR THE PROGRAM.",
        ],
        aliases=["Server Side Public License", "SSPL"],
        version="1",
        osi_approved=False,
    ),
    "SUL-1.0": LegalText(
        "SUL-1.0", "Sustainable Use License v1.0",
        [
            "You may use, copy, distribute, and modify the software for your internal "
            "business purposes.",
            "You may not use the software to provide a commercial service to third parties.",
            "The software is provided as-is, without warranty of any kind.",
        ],
        aliases=["Sustainable Use License", "SUL"],
        version="1.0",
        osi_approved=False,
    ),
}

#: Representative custom / proprietary declarations.  §3.2.2 registers such
#: declarations as LIC-XXXX entries; the demo ships three recurring shapes.
CUSTOM_TEXTS: Dict[str, List[str]] = {
    "Proprietary": [
        "All rights reserved. This software and its source code are proprietary and "
        "confidential.",
        "You may not copy, modify, distribute, sublicense, or reverse engineer this "
        "software without the prior written permission of the copyright holder.",
        "Commercial use requires a separate paid license agreement.",
        "Redistribution of this software in source or binary form is prohibited.",
    ],
    "Internal-Use": [
        "This skill is provided for internal use only.",
        "You may not distribute or sublicense this skill or any of its assets outside your "
        "organization.",
        "No warranty of any kind is provided for internal use.",
    ],
    "Attribution-Required": [
        "You are free to use and modify this skill for any purpose.",
        "You must attribute the original author in any redistributed derivative work and "
        "include a copy of this notice.",
    ],
}


def standard_license_ids() -> List[str]:
    return sorted(LICENSE_TEXTS)


def clauses_for(license_id: str) -> List[str]:
    """Return the clause sentences of a standard license (empty when unknown)."""
    entry = LICENSE_TEXTS.get(license_id)
    return list(entry.clauses) if entry else []
