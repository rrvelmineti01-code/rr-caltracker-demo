"""Evaluate the local whole-dish model on a supplied weighed-meal manifest.

CSV columns: image_path, measured_food_g
Paths are relative to the manifest's directory unless absolute.
Use FOOD-ONLY cooked edible weights, with the container tared. Prefer overhead
photos. The script does not copy photos or send them to providers. The output
has aggregate metrics only, with no image paths or meal descriptions.
This is not a Gemini benchmark and does not test per-ingredient calorie accuracy.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from portion_estimator import predict_mass


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path)
    parser.add_argument('--output',type=Path,default=Path('metrics.json'))
    args=parser.parse_args()
    errors=[]
    percentages=[]
    signed=[]
    with args.manifest.open(newline='',encoding='utf-8-sig') as handle:
        for line,row in enumerate(csv.DictReader(handle),start=2):
            actual=float(row['measured_food_g'])
            if not math.isfinite(actual) or not 1<=actual<=5000:
                raise ValueError(f'Invalid measured food weight at row {line}.')
            image=Path(row['image_path'])
            if not image.is_absolute(): image=args.manifest.parent/image
            predicted=predict_mass(image.read_bytes()).grams
            errors.append(abs(predicted-actual))
            percentages.append(abs(predicted-actual)/actual*100)
            signed.append(predicted-actual)
    if not errors: raise ValueError('The manifest has no examples.')
    metrics={'examples':len(errors),'mass_mae_g':sum(errors)/len(errors),
             'mass_mape_percent':sum(percentages)/len(percentages),
             'mean_signed_error_g':sum(signed)/len(signed),
             'within_15_percent_fraction':sum(e<=15 for e in percentages)/len(errors),
             'scope':'Whole-dish weight only; no Gemini, component allocation or nutrition evaluation.'}
    args.output.write_text(json.dumps(metrics,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(metrics,indent=2))


if __name__=='__main__': main()
