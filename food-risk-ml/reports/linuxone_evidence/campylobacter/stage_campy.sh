#!/bin/bash
# Campylobacter on LinuxONE: install commit 9e88069 beside the previous copy, verify data, test, prepare, train, serve.
set -u
COMMIT=9e88069
E=~/tracefront-evidence; C=$E/campylobacter; mkdir -p $C
T=~/tracefront
if [ ! -f $T/food-risk-ml/.commit_$COMMIT ]; then
  mv $T/food-risk-ml $T/food-risk-ml-salmonella-run          # keeps the Salmonella run's code, registry and reports
  mkdir -p $T/food-risk-ml && tar -xzf /tmp/code-$COMMIT.tgz -C $T/food-risk-ml
  cp -r $T/food-risk-ml-salmonella-run/data/raw/fsis_raw_poultry $T/food-risk-ml/data/raw/
  touch $T/food-risk-ml/.commit_$COMMIT
fi
cd $T/food-risk-ml
{ echo "utc: $(date -u +%FT%TZ)  host: $(hostname)  arch: $(uname -m)"; echo "code: git archive of commit $COMMIT"
  echo "tarball sha256: $(sha256sum /tmp/code-$COMMIT.tgz | cut -d' ' -f1)"; } > $C/10_code.log
R="$E/run_step.sh"
TAIL=4 $R campylobacter/11_verify_data python reports/linuxone_evidence/verify_data.py
TAIL=3 $R campylobacter/12_tests_s390x python -m pytest -q -p no:cacheprovider -o addopts= -W ignore
Z=$(ls data/raw/fsis_raw_poultry/zips/*.zip)
TAIL=3 $R campylobacter/13_prepare python -m src.cli --pathogen campylobacter prepare $Z
grep -q "exit_code: 0" $C/13_prepare.log || { echo "PREPARE FAILED"; exit 1; }
TAIL=30 $R campylobacter/14_train python -m src.cli --pathogen campylobacter train
cp reports/campylobacter/final_model.json reports/campylobacter/metrics.csv $C/
cp "$(ls -d artifacts/registry_campylobacter/*/ | tail -1)metadata.json" $C/registry_metadata.json
echo DONE
