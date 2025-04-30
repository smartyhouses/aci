#! /bin/bash

alembic upgrade head
python -m aci.cli populate-subscription-plans --skip-dry-run
