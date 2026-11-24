"""
generar_banner.py — Genera streamlit/banner.png, el encabezado de la app.

Usa los mismos colores que el banner institucional (degradado magenta → azul),
para que los dos banners se vean como un conjunto.

Uso (desde la raíz del proyecto):

    python Utilidades/generar_banner.py
"""

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')                                   # sin ventana: solo genera el archivo
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch, Circle, Polygon

from utils import STREAMLIT_PATH


ANCHO, ALTO, DPI = 1600, 160, 100
MAGENTA, AZUL, AZUL_OSCURO = '#C2185B', '#2A4A9B', '#123A7A'
DESTINO = f'{STREAMLIT_PATH}/banner.png'


def dibujar_auto(eje, x, y, escala, color='white'):
    """Silueta sencilla de un auto: carrocería, cabina, ventanas y dos ruedas."""
    eje.add_patch(FancyBboxPatch((x, y + 0.18 * escala), 1.0 * escala, 0.28 * escala,
                                 boxstyle='round,pad=0,rounding_size=0.08', fc=color, ec='none'))
    eje.add_patch(Polygon([(x + 0.22 * escala, y + 0.46 * escala), (x + 0.36 * escala, y + 0.70 * escala),
                           (x + 0.70 * escala, y + 0.70 * escala), (x + 0.84 * escala, y + 0.46 * escala)],
                          closed=True, fc=color, ec='none'))
    for x0, x1 in [(0.30, 0.50), (0.53, 0.72)]:                    # ventanas
        eje.add_patch(Polygon([(x + x0 * escala, y + 0.49 * escala), (x + (x0 + 0.06) * escala, y + 0.64 * escala),
                               (x + x1 * escala, y + 0.64 * escala), (x + (x1 + 0.05) * escala, y + 0.49 * escala)],
                              closed=True, fc=AZUL_OSCURO, ec='none', alpha=0.55))
    for xr in (0.24, 0.76):                                         # ruedas
        eje.add_patch(Circle((x + xr * escala, y + 0.18 * escala), 0.12 * escala, fc=AZUL_OSCURO, ec=color, lw=3))
        eje.add_patch(Circle((x + xr * escala, y + 0.18 * escala), 0.05 * escala, fc=color, ec='none'))


def generar():
    fig = plt.figure(figsize=(ANCHO / DPI, ALTO / DPI), dpi=DPI)
    eje = fig.add_axes([0, 0, 1, 1])
    eje.set_xlim(0, ANCHO / ALTO)
    eje.set_ylim(0, 1)
    eje.axis('off')

    # Fondo: degradado horizontal magenta → azul
    degradado = LinearSegmentedColormap.from_list('liacd', [MAGENTA, AZUL, AZUL_OSCURO])
    eje.imshow(np.linspace(0, 1, 512).reshape(1, -1), aspect='auto', cmap=degradado,
               extent=[0, ANCHO / ALTO, 0, 1])

    # Línea de "camino" y auto
    eje.plot([0.45, 1.95], [0.15, 0.15], color='white', lw=2, alpha=0.6)
    dibujar_auto(eje, 0.70, 0.10, escala=1.0)

    # Textos
    eje.text(2.35, 0.60, '¿Cuánto vale mi carro?', color='white', fontsize=38, fontweight='bold', va='center')
    eje.text(2.37, 0.27, 'Valuador y explorador de autos usados  ·  189,845 anuncios de Cars.com (EE. UU.)',
             color='white', fontsize=15, va='center', alpha=0.95)

    os.makedirs(STREAMLIT_PATH, exist_ok=True)
    fig.savefig(DESTINO, dpi=DPI)
    plt.close(fig)
    print(f'Banner guardado en: {os.path.relpath(DESTINO)}')


if __name__ == '__main__':
    generar()
