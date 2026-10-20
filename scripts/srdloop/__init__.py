"""The SRD rule-audit loop: the deterministic half (see docs/srd-rule-loop-plan.md).

Claude agents judge; this package decides what each agent sees, checks what it produced,
keeps per-unit state and reports. Run it as ``python -m scripts.srdloop <command>``.
"""
