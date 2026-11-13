"""License term ontology and legal attitudes (paper Table 1 and Table 2).

A *term* denotes a neutral action space (copy, modify, distribute, ...).  A
*legal attitude* qualifies how strongly the licensor constrains that action:

    CAN     the licensee may perform the term without further condition
    CANNOT  the licensee is prohibited, with no exception
    MUST    the licensee may perform the term only if a condition is met

A term carries three pieces of declarative knowledge used by the offline
reader (`understand.reader.HeuristicLicenseReader`):

    patterns  regexes that surface the term inside a license sentence
    guards    regexes that cancel a match, used to keep the conservative
              reading of the paper (e.g. "modified files must carry notices"
              is an obligation on notices, not a permission to modify)
    examples  a canonical phrase, handy for prompts and for tests
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Optional, Pattern, Sequence, Tuple

ATTITUDES: Tuple[str, ...] = ("CAN", "CANNOT", "MUST")

#: strictness order used by the aggregation operator (paper Table 7, rule A3)
ATTITUDE_RANK: Dict[str, int] = {"CANNOT": 3, "MUST": 2, "CAN": 1}

CATEGORY_RIGHT = "right"          # T1–T18
CATEGORY_OBLIGATION = "obligation"  # T19–T28
CATEGORY_LIABILITY = "liability"  # T29–T31


@dataclass(frozen=True)
class Term:
    tid: str
    name: str
    category: str
    definition: str
    patterns: Sequence[str]
    guards: Sequence[str] = ()
    example: str = ""

    def compiled(self) -> Tuple[Pattern[str], ...]:
        return tuple(re.compile(p, re.IGNORECASE) for p in self.patterns)

    def compiled_guards(self) -> Tuple[Pattern[str], ...]:
        return tuple(re.compile(p, re.IGNORECASE) for p in self.guards)


# --------------------------------------------------------------------------- #
# 31 terms (paper Table 1)
# --------------------------------------------------------------------------- #
TERMS: Tuple[Term, ...] = (
    Term(
        "T1", "Copy", CATEGORY_RIGHT, "reproduce the original work in copies",
        (r"\bcopy(?:ies|ing)?\b", r"\breproduc\w+\b", r"\bverbatim copies\b"),
        guards=(
            # "included in all copies" / "each copy" constrain notices, not copying
            r"\b(?:in|all|each|any) (?:all )?copies\b.{0,20}\b(?:shall|must|includ)",
            r"\b(?:copyright|permission|attribution) notices?\b",
            r"\bcopy of (?:this|the) licen[cs]e\b",
            r"\bcopy of (?:this|the|such) notice\b",
            r"\b(?:possession|recipients?|receives?)\b[^.;]{0,25}\bcopy\b",
        ),
        example="permission is hereby granted ... to copy the Software",
    ),
    Term(
        "T2", "Modify", CATEGORY_RIGHT, "modify the software and create derivatives",
        (r"\bmodif(?:y|ies|ied|ication)\b", r"\bderivative works?\b",
         r"\bprepare derivative\b", r"\bmodified versions?\b",
         r"\badapt\w*\b", r"\bremix\b"),
        guards=(
            # obligations attached to *modified files* target T19/T20, not T2
            r"\bmodif\w+ files?\b",
            r"\bcopy of (?:this|the) licen[cs]e\b",
            r"\b(?:retain|preserve)\b[^.;]{0,160}\b(?:notices?|copyright)\b",
            r"\b(?:copyright|attribution) notices?\b",
        ),
        example="the rights to ... modify ... the Software",
    ),
    Term(
        "T3", "Distribute", CATEGORY_RIGHT, "distribute original or modified derivative works",
        (r"\bdistribut\w+\b", r"\bredistribut\w+\b", r"\bconvey\w*\b", r"\bre-?distribut\w+\b"),
        guards=(
            r"\b(?:retain|preserve)\b[^.;]{0,160}\b(?:notices?|copyright)\b",
            # "Redistributions of source code must retain ... notice" is a notice duty
            r"\b(?:copyright|attribution) notices?\b",
        ),
        example="distribute copies of the Software",
    ),
    Term(
        "T4", "Combine / Link", CATEGORY_RIGHT,
        "permission to combine with external libraries or components",
        (r"\bcombin\w+\b", r"\blink(?:ed|ing)?\b", r"\bincorporat\w+\b", r"\bmerge\b"),
        guards=(
            r"\bcombined work\b.{0,40}\b(?:must|shall)\b",
            r"\blink to the licen[cs]e\b",
        ),
        example="merge the Software with other programs",
    ),
    Term(
        "T5", "Commercial Use", CATEGORY_RIGHT, "use the software for commercial purposes",
        (r"\bcommercial\w*\b", r"\bsell(?:ing)?\b", r"\bsale of\b", r"\bmonetiz\w+"),
        guards=(r"\bnon-?commercial\b.{0,20}\b(?:use|purpose)",),
        example="use the Software for commercial purposes",
    ),
    Term(
        "T6", "Competitive Use", CATEGORY_RIGHT,
        "use the software to develop products that directly compete with the licensor's",
        (r"\bcompet(?:e|es|ing|itive|itor)\w*\b", r"\bcompeting (?:product|service)"),
        example="develop a competing product",
    ),
    Term(
        "T7", "Private Use", CATEGORY_RIGHT,
        "use or modify the software privately without distributing it",
        (r"\bprivate\w* use\b", r"\bpersonal use\b",
         r"\binternal business purposes?\b", r"\binternally\b"),
        example="use the Software for your internal business purposes",
    ),
    Term(
        "T8", "Network Service Provision", CATEGORY_RIGHT,
        "provide software services to users over a network without distributing copies",
        (r"\bsoftware as a service\b", r"\bsaas\b", r"\bpaas\b",
         r"\bmanaged service\b", r"\bas a service\b",
         r"\bover a (?:computer )?network\b", r"\bnetwork service\b"),
        example="provide the Software to others as a managed service",
    ),
    Term(
        "T9", "Sublicense", CATEGORY_RIGHT,
        "re-grant the permitted rights to subsequent third parties",
        (r"\bsub-?licens\w+\b", r"\bre-?grant\w*\b"),
        example="sublicense the Software",
    ),
    Term(
        "T10", "Grant Patents", CATEGORY_RIGHT,
        "grant rights to use patented claims by the licensor or contributors",
        (r"\bpatent\w*\b",),
        guards=(r"\b(?:retain|preserve|includ)\w*\b[^.;]{0,160}\bpatent\b",),
        example="grants a patent license to the Work",
    ),
    Term(
        "T11", "Use TradeMark", CATEGORY_RIGHT,
        "use contributor's name, trademark or logo",
        (r"\btrade ?marks?\b", r"\btrade names?\b", r"\blogos?\b", r"\bservice marks?\b"),
        guards=(r"\b(?:retain|preserve|includ)\w*\b[^.;]{0,160}\btrade ?marks?\b",),
        example="use the trade names or trademarks of the Licensor",
    ),
    Term(
        "T12", "Warranty", CATEGORY_RIGHT,
        "offer or provide warranty protection or other support for the software",
        (r"\bwarrant(?:y|ies)\b",),
        example="without warranty of any kind",
    ),
    Term(
        "T13", "Add License Terms", CATEGORY_RIGHT,
        "provide additional license terms in derivative works",
        (r"\badditional (?:or different )?(?:license )?(?:terms|conditions)\b",
         r"\bdifferent (?:license )?terms\b", r"\bfurther restrictions?\b",
         r"\badditional restrictions?\b"),
        example="you may provide additional or different license terms",
    ),
    Term(
        "T14", "Charge Distribution Fee", CATEGORY_RIGHT,
        "charge a fee for distributing copies of the software",
        (r"\bcharge (?:a )?fee\b", r"\bcharge\b.{0,30}\bfee\b", r"\bfee for\b", r"\bprice\b"),
        example="you may charge a fee for the physical act of transferring a copy",
    ),
    Term(
        "T15", "Publicly Display", CATEGORY_RIGHT, "display the original work publicly",
        (r"\bpublicly display\w*\b", r"\bdisplay\w*\b", r"\bmake available\b.{0,20}\bpublicly\b"),
        example="publicly display the Work",
    ),
    Term(
        "T16", "Publicly Perform", CATEGORY_RIGHT, "perform the original work publicly",
        (r"\bpublicly perform\w*\b", r"\bperform\w* publicly\b"),
        example="publicly perform the Work",
    ),
    Term(
        "T17", "Reverse Engineering", CATEGORY_RIGHT,
        "reverse engineer, decompile or disassemble the software",
        (r"\breverse engineer\w*\b", r"\bdecompil\w+\b", r"\bdisassembl\w+\b"),
        example="you may not reverse engineer the Software",
    ),
    Term(
        "T18", "AI Training", CATEGORY_RIGHT,
        "use the software, its outputs or its data for training AI/ML models",
        (r"\btrain\w*\b.{0,40}\b(?:ai|ml|models?|machine learning)\b",
         r"\b(?:ai|ml|machine learning)\b.{0,40}\btrain\w*\b",
         r"\bfine-?tun\w+\b", r"\bmachine learning\b", r"\bmodel training\b"),
        example="use the Work to train machine learning models",
    ),
    Term(
        "T19", "State Changes", CATEGORY_OBLIGATION,
        "state significant changes, cause modified files to carry prominent notices",
        (r"\bprominent notices?\b", r"\bstate\b.{0,20}\bchanges?\b",
         r"\bnotices? stating\b", r"\bindicate\b.{0,30}\bchanges?\b"),
        example="cause modified files to carry prominent notices stating that You changed the files",
    ),
    Term(
        "T20", "Retain Copyright", CATEGORY_OBLIGATION,
        "retain all copyright notices in copies or substantial uses of the work",
        (r"\bcopyright notices?\b", r"\bretain\b[^.;]{0,160}\bcopyright\b",
         r"\bpreserve\b[^.;]{0,160}\bcopyright\b"),
        example="the above copyright notice shall be included in all copies",
    ),
    Term(
        "T21", "Include License", CATEGORY_OBLIGATION,
        "include the full text of the license in all copies or substantial uses",
        (r"\bcopy of (?:this|the) licen[cs]e\b", r"\bpermission notice\b",
         r"\binclud\w*\b.{0,40}\blicen[cs]e\b", r"\bgive\b.{0,40}\bcopy of this licen[cs]e\b"),
        example="a copy of this License must be included",
    ),
    Term(
        "T22", "Include Notice", CATEGORY_OBLIGATION,
        "include any NOTICE text file or attribution notices with derivative works",
        (r"\bnotice (?:text )?file\b", r"\battribution notices?\b",
         r"\bnotice file\b"),
        example="include a readable copy of the attribution notices within the NOTICE file",
    ),
    Term(
        "T23", "Offer Source Code", CATEGORY_OBLIGATION,
        "disclose your source code when you distribute the software",
        (r"\bsource code\b", r"\bcorresponding source\b", r"\bdisclose\b.{0,30}\bsource\b"),
        guards=(
            # "redistributions of source code must retain ..." is a notice duty (T20/T26)
            r"\bredistributions? of source code\b",
            r"\b(?:retain|preserve)\b[^.;]{0,160}\bnotices?\b",
        ),
        example="you must offer the Corresponding Source to all recipients",
    ),
    Term(
        "T24", "Network Source Disclosure", CATEGORY_OBLIGATION,
        "provide the corresponding source code to users interacting with the software over a network",
        (r"\b(?:network|remote\w*)\b.{0,90}\b(?:source code|corresponding source)\b",
         r"\b(?:source code|corresponding source)\b.{0,90}\b(?:network|remote\w*)\b"),
        example="users interacting with it remotely shall be offered the Corresponding Source",
    ),
    Term(
        "T25", "Rename Derivative", CATEGORY_OBLIGATION,
        "change the name of the derivative work to avoid misrepresenting it as the original",
        (r"\brenam\w+\b", r"\bchang\w+\b.{0,30}\bname\b", r"\bdifferent name\b"),
        example="you must rename modified versions of the Work",
    ),
    Term(
        "T26", "Retain Disclaimer", CATEGORY_OBLIGATION,
        "retain any disclaimer of warranty in redistributions",
        (r"\bdisclaimer\b",),
        example="retain the disclaimer of warranty",
    ),
    Term(
        "T27", "Give Credit", CATEGORY_OBLIGATION,
        "give explicit credit or acknowledgement to the author",
        (r"\bcredit\b", r"\backnowledg\w+\b", r"\battribution\b"),
        guards=(r"\battribution notices?\b",),
        example="you must give appropriate credit to the author",
    ),
    Term(
        "T28", "Include Install Instructions", CATEGORY_OBLIGATION,
        "include build & install instructions necessary to modify and reinstall the software",
        (r"\binstall\w*\b.{0,40}\binstructions?\b", r"\bbuild\b.{0,30}\binstructions?\b"),
        example="accompany it with the installation information",
    ),
    Term(
        "T29", "No Liability", CATEGORY_LIABILITY,
        "the licensor cannot be held liable for damages arising from the use of the software",
        (r"\bliabilit(?:y|ies)\b", r"\bliabl\w+\b", r"\bdamages\b"),
        example="in no event shall the authors be liable for any damages",
    ),
    Term(
        "T30", "ShareAlike", CATEGORY_OBLIGATION,
        "distribute derivatives under the same or a compatible license (weak copyleft)",
        (r"\bshare-?alike\b", r"\bsame or (?:a )?compatible\b",
         r"\bcompatible licen[cs]e\b", r"\bmpl\b.{0,30}\bcompatible\b"),
        guards=(r"\bsubject to the terms and conditions\b",),
        example="distribute your contributions under the same license as the original",
    ),
    Term(
        "T31", "Keep Same License", CATEGORY_OBLIGATION,
        "distribute derivatives under the exact same license (strong copyleft)",
        (r"\bsame licen[cs]e\b", r"\bidentical licen[cs]e\b",
         r"\bunder (?:the )?(?:same|this) licen[cs]e\b",
         r"\blicensed as a whole\b", r"\bunder the terms of this licen[cs]e\b"),
        guards=(
            # clauses about *not* imposing further restrictions are the negation of T31
            r"\bfurther restrictions?\b",
            r"\bpropagate\b",
            r"\bdoes not\b[^.;]{0,40}\blimit\b",
            r"\bwarrant\w*",
            r"\bdisclaim\w*",
        ),
        example="you must license the entire work under this License",
    ),
)

TERM_BY_ID: Dict[str, Term] = {t.tid: t for t in TERMS}
TERM_BY_NAME: Dict[str, Term] = {t.name: t for t in TERMS}

#: terms covered by rule D1 (default CAN when never mentioned)
OBLIGATION_TERMS: Tuple[str, ...] = tuple(
    t.tid for t in TERMS if t.category in (CATEGORY_OBLIGATION, CATEGORY_LIABILITY)
)
#: terms covered by rules D2 / D3 (default depends on the catch-all grant)
RIGHT_TERMS: Tuple[str, ...] = tuple(t.tid for t in TERMS if t.category == CATEGORY_RIGHT)

#: Terms that can make two licenses *incompatible*.
#:
#: Compatibility is only broken by terms that change the conditions under which
#: the composite work can be distributed: restrictions on the granted rights
#: (T2, T3, T5, T6, T8, T9, T17, T18), the freedom to attach terms (T13) and
#: obligations that force terms onto derivative works (T23, T24, T30, T31).
#:
#: Formalities stack instead of conflicting — every license's notice, file
#: marking and warranty disclaimer can be carried by the same distribution at
#: the same time (T14, T19–T22, T25–T29).  They are therefore excluded from the
#: compatibility judgement while remaining part of the ontology, of the term
#: database and of the audit report.  This matches the conflict-term
#: distribution reported in Table 16 and Table 18 of the paper.
CONFLICT_TERMS: Tuple[str, ...] = (
    "T2", "T3", "T5", "T6", "T8", "T9", "T13",
    "T17", "T18", "T23", "T24", "T30", "T31",
)


# --------------------------------------------------------------------------- #
# Legal modality cues (paper Table 2)
# --------------------------------------------------------------------------- #
#: R6 — "may not ... without prior written permission" is MUST, not CANNOT
RE_CONDITIONAL_PROHIBITION = re.compile(
    r"\b(?:may|shall|must|is|are)\b[^.;]{0,40}\bwithout\b[^.;]{0,60}"
    r"\b(?:permission|consent|authori[sz]ation|licen[cs]e|agreement)\b",
    re.IGNORECASE,
)

RE_CANNOT = re.compile(
    r"\b(?:shall|must|may|can|will|is|are|does)\s+not\b"
    r"|\bmay\s+not\b"
    r"|\bnot\s+(?:be\s+)?(?:permitted|allowed|granted)\b"
    r"|\bprohibit\w*|\bforbid\w*"
    r"|\bno\s+(?:one|person|entity|party|part)\b[^.;]{0,40}\b(?:may|shall|is)\b"
    r"|\bis\s+not\s+allowed\b"
    r"|\bin\s+no\s+event\b|\bunder\s+no\s+(?:circumstances|legal\s+theory)\b"
    r"|\bwithout\s+(?:any\s+)?(?:warranty|warranties|liabilit|guarantee)"
    r"|\bno\s+warrant(?:y|ies)\b"
    r"|\bnot\s+granted\b",
    re.IGNORECASE,
)

#: Warranty disclaimers ("AS IS", "disclaimed", "without warranty") belong to T12
#: alone — treating them as a clause-wide prohibition would wrongly ban every
#: other term of the same sentence (e.g. "retain the copyright notice and this
#: disclaimer").
RE_TERM_CANNOT = {
    "T12": re.compile(
        r"\bwithout\b[^.;]{0,40}\bwarrant|\bno\s+warrant|disclaim\w*|\bas\s+is\b",
        re.IGNORECASE,
    ),
}

RE_MUST = re.compile(
    r"\b(?:shall|must|need\s+to|required\s+to|is\s+required|are\s+required|requires)\b"
    r"|\bonly\s+if\b|\bprovided\s+that\b"
    r"|\bconditioned?\s+(?:on|upon|that)\b|\bin\s+order\s+to\b",
    re.IGNORECASE,
)

RE_CAN = re.compile(
    r"\b(?:may|can|permitted|allowed|free\s+to|entitled\s+to|has\s+the\s+right\s+to"
    r"|is\s+granted|are\s+granted|hereby\s+grants?|grants?)\b"
    r"|\bwithout\s+restriction\b|\bfor\s+any\s+purpose\b|\bno-charge\b|\broyalty-free\b",
    re.IGNORECASE,
)

#: catch-all grant markers used by rule D2 (Grant(l) = 1)
RE_GRANT_CUE = re.compile(
    r"\bwithout\s+restriction\b|\bwithout\s+limitation\b|\bfor\s+any\s+purpose\b"
    r"|\bany\s+purpose\b|\bno-charge\b|\broyalty-free\b|\bfree\s+of\s+charge\b"
    r"|\bat\s+no\s+charge\b|\bunrestricted\b|\bperpetual\b|\birrevocable\b"
    r"|\bare\s+permitted\b",
    re.IGNORECASE,
)

#: condition markers used to scope a MUST (paper §3.4.2, function E)
RE_CONDITION_MARKER = re.compile(
    r"\b(?:provided\s+that|only\s+if|on\s+the\s+condition\s+that"
    r"|without\s+(?:the\s+)?(?:prior\s+)?(?:written\s+)?(?:permission|consent)"
    r"|so\s+long\s+as|as\s+long\s+as)\b",
    re.IGNORECASE,
)

#: clause separators used by the sentence-level reader
RE_CLAUSE_SPLIT = re.compile(r"[;:]|\s+but\s+|\s+however\s*,?", re.IGNORECASE)


def is_obligation(term_id: str) -> bool:
    """True for T19–T31, the group covered by default rule D1."""
    return term_id in OBLIGATION_TERMS


def term(tid_or_name: str) -> Optional[Term]:
    """Look up a term by id ("T5") or by name ("Commercial Use")."""
    return TERM_BY_ID.get(tid_or_name) or TERM_BY_NAME.get(tid_or_name)


def strictest(attitudes: Sequence[str]) -> Optional[str]:
    """Aggregation operator ⊙ (paper Table 7 A3): CANNOT ≻ MUST ≻ CAN."""
    best: Optional[str] = None
    for a in attitudes:
        if a not in ATTITUDE_RANK:
            raise ValueError(f"unknown attitude: {a!r}")
        if best is None or ATTITUDE_RANK[a] > ATTITUDE_RANK[best]:
            best = a
    return best
