#!/usr/bin/env bash
set -euo pipefail

HARNESS="/home/smlflg/Projekte/FirstRealHarnessEvaluation_KarpathiesMD/harness"
BASELINE="$HARNESS/CONVENTIONS.baseline.md"

extract_rule() {
    local rule_file="$1"
    local out
    out=$(sed -n '/^## R[0-9]/,/^$/p' "$rule_file" | head -n -1)
    echo "$out"
}

mkdir -p "$HARNESS"

# Generate each combination
echo "=== Generating 11 CONVENTIONS files ==="

# B: Baseline only
cp "$BASELINE" "$HARNESS/CONVENTIONS.B.md"
echo "  B: CONVENTIONS.B.md"

# R1, R2, R3, R4 (single rules)
for r in R01 R02 R03 R04; do
    cat "$BASELINE" > "$HARNESS/CONVENTIONS.$r.md"
    echo "" >> "$HARNESS/CONVENTIONS.$r.md"
    extract_rule "$HARNESS/CONVENTIONS.v0_plus_$r.md" >> "$HARNESS/CONVENTIONS.$r.md"
    echo "  $r: CONVENTIONS.$r.md"
done

# R1+R2
cat "$BASELINE" > "$HARNESS/CONVENTIONS.R01_R02.md"
echo "" >> "$HARNESS/CONVENTIONS.R01_R02.md"
extract_rule "$HARNESS/CONVENTIONS.v0_plus_R01.md" >> "$HARNESS/CONVENTIONS.R01_R02.md"
echo "" >> "$HARNESS/CONVENTIONS.R01_R02.md"
extract_rule "$HARNESS/CONVENTIONS.v0_plus_R02.md" >> "$HARNESS/CONVENTIONS.R01_R02.md"
echo "  R01_R02: CONVENTIONS.R01_R02.md"

# R1+R3
cat "$BASELINE" > "$HARNESS/CONVENTIONS.R01_R03.md"
echo "" >> "$HARNESS/CONVENTIONS.R01_R03.md"
extract_rule "$HARNESS/CONVENTIONS.v0_plus_R01.md" >> "$HARNESS/CONVENTIONS.R01_R03.md"
echo "" >> "$HARNESS/CONVENTIONS.R01_R03.md"
extract_rule "$HARNESS/CONVENTIONS.v0_plus_R03.md" >> "$HARNESS/CONVENTIONS.R01_R03.md"
echo "  R01_R03: CONVENTIONS.R01_R03.md"

# R1+R4
cat "$BASELINE" > "$HARNESS/CONVENTIONS.R01_R04.md"
echo "" >> "$HARNESS/CONVENTIONS.R01_R04.md"
extract_rule "$HARNESS/CONVENTIONS.v0_plus_R01.md" >> "$HARNESS/CONVENTIONS.R01_R04.md"
echo "" >> "$HARNESS/CONVENTIONS.R01_R04.md"
extract_rule "$HARNESS/CONVENTIONS.v0_plus_R04.md" >> "$HARNESS/CONVENTIONS.R01_R04.md"
echo "  R01_R04: CONVENTIONS.R01_R04.md"

# R2+R3
cat "$BASELINE" > "$HARNESS/CONVENTIONS.R02_R03.md"
echo "" >> "$HARNESS/CONVENTIONS.R02_R03.md"
extract_rule "$HARNESS/CONVENTIONS.v0_plus_R02.md" >> "$HARNESS/CONVENTIONS.R02_R03.md"
echo "" >> "$HARNESS/CONVENTIONS.R02_R03.md"
extract_rule "$HARNESS/CONVENTIONS.v0_plus_R03.md" >> "$HARNESS/CONVENTIONS.R02_R03.md"
echo "  R02_R03: CONVENTIONS.R02_R03.md"

# R2+R4
cat "$BASELINE" > "$HARNESS/CONVENTIONS.R02_R04.md"
echo "" >> "$HARNESS/CONVENTIONS.R02_R04.md"
extract_rule "$HARNESS/CONVENTIONS.v0_plus_R02.md" >> "$HARNESS/CONVENTIONS.R02_R04.md"
echo "" >> "$HARNESS/CONVENTIONS.R02_R04.md"
extract_rule "$HARNESS/CONVENTIONS.v0_plus_R04.md" >> "$HARNESS/CONVENTIONS.R02_R04.md"
echo "  R02_R04: CONVENTIONS.R02_R04.md"

# R3+R4
cat "$BASELINE" > "$HARNESS/CONVENTIONS.R03_R04.md"
echo "" >> "$HARNESS/CONVENTIONS.R03_R04.md"
extract_rule "$HARNESS/CONVENTIONS.v0_plus_R03.md" >> "$HARNESS/CONVENTIONS.R03_R04.md"
echo "" >> "$HARNESS/CONVENTIONS.R03_R04.md"
extract_rule "$HARNESS/CONVENTIONS.v0_plus_R04.md" >> "$HARNESS/CONVENTIONS.R03_R04.md"
echo "  R03_R04: CONVENTIONS.R03_R04.md"

echo ""
echo "=== 11 files generated ==="
ls -la "$HARNESS"/CONVENTIONS.{B,R01,R02,R03,R04,R01_R02,R01_R03,R01_R04,R02_R03,R02_R04,R03_R04}.md
