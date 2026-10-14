"""Thin entry point: the worker logic lives in ledgeit_api.anchoring (shares DB + proof-core code)."""

from ledgeit_api.anchoring.run import main

raise SystemExit(main())
