import os

sizes = [72, 96, 128, 144, 192, 512]
icons_dir = '/Users/mac/Desktop/py-voip/frontend/public/icons'
os.makedirs(icons_dir, exist_ok=True)

for size in sizes:
    r = size // 5
    sw = max(2, size // 30)
    cr = size * 0.32
    fs = size * 0.18
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
        f'<rect width="{size}" height="{size}" rx="{r}" fill="#0E2A52"/>'
        f'<g transform="translate({size/2},{size/2})">'
        f'<circle cx="0" cy="0" r="{cr:.1f}" fill="none" stroke="#cfb000" stroke-width="{sw}"/>'
        f'<text x="0" y="{fs:.1f}" text-anchor="middle" font-family="Inter,sans-serif" font-weight="700" font-size="{fs:.1f}" fill="white">VL</text>'
        f'</g></svg>'
    )
    with open(os.path.join(icons_dir, f'icon-{size}.svg'), 'w') as f:
        f.write(svg)
    print(f'Created icon-{size}.svg')

print('Done')
