"""Fetch OFL font sources from Google Fonts and instantiate regular/bold faces.
Run using the backend environment (fonttools required). Never needed at runtime.
"""
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import quote
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
import tempfile
root=Path(__file__).resolve().parents[1]
files={'Inter':'Inter[opsz,wght].ttf','Poppins':'Poppins-Regular.ttf','Montserrat':'Montserrat[wght].ttf','Anton':'Anton-Regular.ttf','Bebas Neue':'BebasNeue-Regular.ttf','Oswald':'Oswald[wght].ttf','DM Sans':'DMSans[opsz,wght].ttf'}
for family,filename in files.items():
    slug=family.lower().replace(' ','')
    base=f'https://raw.githubusercontent.com/google/fonts/main/ofl/{slug}/'
    out=root/'backend/fonts';out.mkdir(exist_ok=True)
    (out/f'{slug}-OFL.txt').write_bytes(urlopen(base+'OFL.txt',timeout=30).read())
    for weight in [400,700]:
        sourcefile='Poppins-Bold.ttf' if family=='Poppins' and weight==700 else filename
        raw=urlopen(base+quote(sourcefile),timeout=30).read()
        with tempfile.NamedTemporaryFile(suffix='.ttf') as temp:
            temp.write(raw);temp.flush();font=TTFont(temp.name)
            if 'fvar' in font:
                axes={a.axisTag:(weight if a.axisTag=='wght' else a.defaultValue) for a in font['fvar'].axes}
                font=instantiateVariableFont(font,axes,inplace=False)
            # A stable family name shared by browser and libass; upstream OFL retained.
            for name in font['name'].names:
                if name.nameID in (1,16): name.string=family.encode(name.getEncoding(),errors='replace')
            font.save(out/f'{slug}-{weight}.ttf')
            if family=='Inter' and weight==400:
                font.save(root/'frontend/public/fonts/inter.ttf')
    print(f'Installed {family}',flush=True)
(root/'frontend/public/fonts/Inter-OFL.txt').write_bytes((root/'backend/fonts/inter-OFL.txt').read_bytes())
