#!/bin/bash
# Imidacloprid chemical model on LinuxONE: install commit 6513e9f (code + Person A's handoff files, exact bytes),
# gate the handoff (hash pins), test, train.
set -u
COMMIT=6513e9f
E=~/tracefront-evidence; C=$E/chemical; mkdir -p $C
T=~/tracefront
if [ ! -f $T/food-risk-ml/.commit_$COMMIT ]; then
  mv $T/food-risk-ml $T/food-risk-ml-9e88069                 # keeps the Campylobacter run's code, registry and reports
  mkdir -p $T/stage && tar -xzf /tmp/chem-$COMMIT.tgz -C $T/stage
  mv $T/stage/food-risk-ml $T/food-risk-ml
  mkdir -p $T/data $T/reports && cp -r $T/stage/data/processed $T/data/ && cp $T/stage/reports/m7_validation.json $T/reports/
  rm -rf $T/stage
  cp -r $T/food-risk-ml-9e88069/data/raw/fsis_raw_poultry $T/food-risk-ml/data/raw/
  touch $T/food-risk-ml/.commit_$COMMIT
fi
cd $T/food-risk-ml
{ echo "utc: $(date -u +%FT%TZ)  host: $(hostname)  arch: $(uname -m)"; echo "code + handoff: git archive of commit $COMMIT"
  echo "tarball sha256: $(sha256sum /tmp/chem-$COMMIT.tgz | cut -d' ' -f1)"
  echo "== Person A handoff files (sha256)"; sha256sum $T/data/processed/* $T/reports/m7_validation.json; } > $C/20_code.log
R="$E/run_step.sh"
TAIL=3 $R chemical/21_check_handoff python -m src.cli check-handoff ../data/processed/chemical_imidacloprid_detection_training_v1.readiness.json
grep -q "exit_code: 0" $C/21_check_handoff.log || { echo "GATE FAILED"; exit 1; }
TAIL=3 $R chemical/22_tests_s390x python -m pytest -q -p no:cacheprovider -o addopts= -W ignore
TAIL=40 $R chemical/23_train python -m src.cli train-chemical
cp reports/chemical_imidacloprid/final_model.json reports/chemical_imidacloprid/metrics.csv $C/
cp "$(ls -d artifacts/registry_chemical_imidacloprid/*/ | tail -1)metadata.json" $C/registry_metadata.json
echo DONE
