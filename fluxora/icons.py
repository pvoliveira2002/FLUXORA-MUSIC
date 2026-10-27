"""Ícones vetoriais desenhados no próprio projeto, sem fontes externas."""
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer

PATHS = {
 'download': '<path d="M12 3v12m-4-4 4 4 4-4"/><path d="M4 17v4h16v-4"/>',
 'library': '<path d="M4 5h16v14H4z"/><path d="M8 5v14M8 9h12"/>',
 'film': '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 5v14M17 5v14M3 9h4m-4 6h4m10-6h4m-4 6h4"/>',
 'convert': '<path d="m7 7-4 4 4 4M3 11h12m2-4 4 4-4 4m4-4H9"/>',
 'monitor': '<rect x="3" y="4" width="18" height="14" rx="2"/><path d="M8 22h8M12 18v4"/>',
 'mic': '<rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v4m-4 0h8"/>',
 'phone': '<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/>',
 'settings': '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a8 8 0 0 0 .1-6l2-1.5-2-3.5L17 5a8 8 0 0 0-5-2l-.6-2h-3l-.5 2A8 8 0 0 0 4 5L1.5 4 0 7.5 2 9a8 8 0 0 0 0 6L0 16.5 1.5 20 4 19a8 8 0 0 0 4 2l.5 2h3l.5-2a8 8 0 0 0 5-2l2.4 1 2-3.5z" transform="translate(1 0) scale(.91)"/>',
 'history': '<circle cx="12" cy="12" r="9"/><path d="M12 6v7l4 2M3 12H1"/>',
 'paste': '<rect x="5" y="5" width="14" height="17" rx="2"/><path d="M9 5V3h6v2M8 10h8m-8 4h8"/>',
 'search': '<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6"/>',
 'play': '<path d="m8 5 11 7-11 7z"/>',
 'pause': '<path d="M8 5v14M16 5v14"/>',
 'check': '<path d="m4 12 5 5L20 6"/>',
 'close': '<path d="M5 5l14 14M19 5 5 19"/>',
 'folder': '<path d="M3 7a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v10H3z"/>',
 'music': '<path d="M9 18V5l12-2v13M9 18a3 3 0 1 1-3-3 3 3 0 0 1 3 3zm12-2a3 3 0 1 1-3-3 3 3 0 0 1 3 3z"/>',
 'list': '<path d="M8 6h13M8 12h13M8 18h13M3 6h1m-1 6h1m-1 6h1"/>',
 'grid': '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>',
 'subtitles': '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M6 12h5m2 0h5M6 16h9"/>',
 'external': '<path d="M13 4h7v7M20 4 10 14"/><path d="M19 14v6H4V5h6"/>',
 'menu': '<path d="M4 6h16M4 12h16M4 18h16"/>',
 'alert': '<circle cx="12" cy="12" r="9"/><path d="M12 7v6m0 4h.01"/>',
 'plus': '<path d="M12 5v14M5 12h14"/>',
 'trash': '<path d="M4 7h16M9 7V4h6v3m3 0-1 14H7L6 7m4 4v6m4-6v6"/>',
 'star': '<path d="m12 3 2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
}

def icon(name: str, color: str = '#A7B8BD', size: int = 21) -> QIcon:
    shapes = PATHS.get(name, PATHS['film'])
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
           f'fill="none" stroke="{color}" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">{shapes}</svg>')
    renderer = QSvgRenderer(QByteArray(svg.encode('utf-8')))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
