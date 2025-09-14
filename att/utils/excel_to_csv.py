#!/usr/bin/env python

import xlrd
import csv
from pathlib import Path

xlsfolder = Path('files')
csvfolder = Path('csvfiles')
csvfolder.mkdir(exist_ok=True)

for xlsfile in xlsfolder.glob(f'*.xls'):
    print(xlsfile)
    if xlsfile.is_file():
        excel = xlrd.open_workbook(str(xlsfile))
        sheet = excel.sheet_by_index(0)
        with open(csvfolder / (xlsfile.stem + ".csv"), 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            for row in range(sheet.nrows):
                writer.writerow(sheet.row_values(row))
