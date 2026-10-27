"""Identidade visual Fluxora 3.0 - painel escuro e verde neon."""
BG = '#080F12'
SIDEBAR = '#081013'
SURFACE = '#101C20'
SURFACE2 = '#142329'
FIELD = '#111E23'
BORDER = '#23363C'
TEXT = '#F0F6F6'
MUTED = '#9CAEB4'
SUBTLE = '#698089'
GREEN = '#A1FF12'
GREEN_DARK = '#193A10'
RED = '#FF797E'

QSS = f'''
* {{ font-family: "Segoe UI", "Arial"; font-size: 12px; color: {TEXT}; outline: 0; }}
QMainWindow, QWidget#Root, QWidget#Body, QStackedWidget {{ background-color: {BG}; }}
QFrame#Sidebar {{ background-color: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
QFrame#Card, QFrame#Panel, QFrame#FormPanel {{ background-color: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#InfoBox {{ background-color: {SURFACE2}; border: 1px solid {BORDER}; border-radius: 10px; }}
QFrame#Thumbnail {{ background-color: #19302C; border-radius: 8px; }}
QFrame#Separator {{ background-color: {BORDER}; max-height: 1px; min-height: 1px; border: 0; }}
QLabel#Brand {{ font-size: 21px; font-weight: 800; letter-spacing: 1px; }}
QLabel#Heading {{ font-size: 24px; font-weight: 750; }}
QLabel#Section {{ font-size: 17px; font-weight: 750; }}
QLabel#Muted {{ color: {MUTED}; }}
QLabel#Subtle {{ color: {SUBTLE}; }}
QLabel#Success {{ color: {GREEN}; font-weight: 700; }}
QLabel#Tag {{ padding: 4px 8px; border-radius: 5px; background: #243238; font-size: 11px; }}
QLabel#Eyebrow {{ font-size: 10px; color: {MUTED}; letter-spacing: 1px; font-weight: 650; }}
QLineEdit {{ background-color: {FIELD}; border: 1px solid {BORDER}; border-radius: 9px; padding: 11px 13px; selection-background-color: #35612D; font-size: 13px; }}
QLineEdit:focus {{ border: 1px solid #66A434; }}
QComboBox {{ background-color: {FIELD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 9px 28px 9px 11px; min-height: 19px; }}
QComboBox:hover {{ border-color: #456252; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right; width: 25px; border: none; }}
QComboBox::down-arrow {{ image: none; border-style: solid; border-width: 5px 4px 0 4px; border-color: {MUTED} transparent transparent transparent; }}
QComboBox QAbstractItemView {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; padding: 5px; selection-background-color: {GREEN_DARK}; selection-color: {TEXT}; }}
QPushButton {{ border: 1px solid {BORDER}; border-radius: 9px; background: {SURFACE}; color: {TEXT}; padding: 10px 15px; font-weight: 550; }}
QPushButton:hover {{ background: #1C3034; border-color: #4E6D68; }}
QPushButton:pressed {{ background: #223B36; }}
QPushButton:disabled {{ color: #6E8183; background: #111B1E; border-color: #202E30; }}
QPushButton#Primary {{ background: {GREEN}; border-color: {GREEN}; color: #0B1607; font-weight: 800; }}
QPushButton#Primary:hover {{ background: #BBFF61; border-color: #BBFF61; }}
QPushButton#Primary:disabled {{ background: #39542D; border-color: #39542D; color: #81947B; }}
QPushButton#Nav {{ border: none; background: transparent; text-align: left; color: #A7B9BB; font-size: 13px; padding: 12px 12px; border-radius: 8px; }}
QPushButton#Nav:hover {{ background: #17252A; color: white; }}
QPushButton#Nav[active="true"] {{ background: #224B0C; color: #F5FFE9; border-left: 3px solid {GREEN}; font-weight: 700; }}
QPushButton#Nav:disabled {{ background: transparent; color: #577077; }}
QPushButton#Chip {{ border: 1px solid {BORDER}; background: {SURFACE}; border-radius: 8px; font-size: 12px; padding: 9px 13px; }}
QPushButton#Chip:checked {{ color: #102207; background: {GREEN}; border-color: {GREEN}; font-weight: 800; }}
QPushButton#Link {{ border: none; background: transparent; color: {GREEN}; padding: 4px; }}
QPushButton#IconButton {{ min-width: 19px; min-height: 20px; padding: 8px; }}
QProgressBar {{ background-color: #26363A; border: 0; border-radius: 3px; max-height: 6px; min-height: 6px; color: transparent; }}
QProgressBar::chunk {{ background: {GREEN}; border-radius: 3px; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: {BG}; width: 8px; border: 0; }}
QScrollBar::handle:vertical {{ background: #314747; border-radius: 4px; min-height: 35px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QTableWidget {{ background: {SURFACE}; alternate-background-color: #111E22; border: 1px solid {BORDER}; border-radius: 10px; gridline-color: {BORDER}; selection-background-color: #244327; selection-color: {TEXT}; }}
QHeaderView::section {{ background: #17252A; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER}; padding: 10px 8px; font-size: 11px; }}
QTableWidget::item {{ padding: 6px; border: 0; }}
QCheckBox {{ color: {TEXT}; spacing: 8px; }}
QCheckBox::indicator {{ width: 17px; height: 17px; border: 1px solid #4B656C; border-radius: 4px; background: {SURFACE2}; }}
QCheckBox::indicator:checked {{ background: {GREEN}; border-color: {GREEN}; }}
QDialog {{ background: {BG}; }}
QTabWidget::pane {{ border: 0; }}
QToolTip {{ color: {TEXT}; background: {SURFACE2}; border: 1px solid {BORDER}; }}
QLabel#ConverterTitle {{ font-size: 21px; font-weight: 800; }}
QLabel#ConverterEmblem {{ color: #91FF00; font-size: 28px; font-weight: 800; min-width: 35px; }}
QLabel#ConverterStrong {{ font-size: 12px; font-weight: 700; }}
QLabel#MediaGlyph {{ background: #0D191C; color: #91FF00; border-radius: 8px; font-size: 19px; font-weight: 800; }}
QLabel#DestinationPath {{ background: #0D191C; border: 1px solid #25383C; border-radius: 7px; padding: 7px 10px; color: #D9E4E5; }}
QLabel#ConverterEmpty {{ color: #697C80; font-size: 13px; padding: 35px; }}
QLabel#ConverterDropFeedback {{ background: #25451B; color: #F2F6F4; border: 1px dashed #91FF00; border-radius: 10px; padding: 9px; font-weight: 700; }}
QFrame#ConverterListPanel, QFrame#ConverterSettings, QFrame#ConverterFixedFooter {{ background: #132024; border: 1px solid #25383C; border-radius: 12px; }}
QFrame#ConverterAdvanced {{ background: #0D191C; border: 1px solid #25383C; border-radius: 10px; }}
QFrame#ConversionCard {{ background: #0D191C; border: 1px solid #1C3034; border-radius: 10px; }}
QFrame#ConversionCard[batchSelected="true"] {{ background: #102022; border-left: 3px solid #91FF00; }}
QSplitter#ConverterWorkspace::handle {{ background: transparent; width: 8px; height: 8px; }}
QPushButton#ConverterAdd {{ min-height: 48px; padding: 8px 18px; background: #91FF00; border-color: #91FF00; color: #0A1607; font-size: 13px; font-weight: 800; }}
QPushButton#ConverterAdd:hover {{ background: #B8FF50; }}
QPushButton#ConverterImport {{ min-height: 48px; padding: 8px 18px; background: #132024; font-size: 13px; font-weight: 700; }}
QPushButton#ConverterTool {{ padding: 6px 8px; min-height: 19px; background: #0D191C; font-size: 11px; }}
QPushButton#CategoryChoice {{ min-height: 30px; background: #213035; padding: 7px; }}
QPushButton#CategoryChoice:checked {{ background: #25451B; color: #91FF00; border-color: #91FF00; font-weight: 800; }}
QComboBox#ConverterFormatSelect {{ min-height: 27px; font-size: 14px; font-weight: 750; }}
QPushButton#ConverterAdvancedToggle {{ background: transparent; border-color: transparent; text-align: left; color: #A2B4B6; padding: 7px 3px; }}
QPushButton#ConverterAdvancedToggle:hover, QPushButton#ConverterAdvancedToggle:checked {{ color: #91FF00; background: #0D191C; }}
QPushButton#CompactSettingsToggle {{ min-height: 31px; text-align: left; background: #132024; border-color: #25383C; color: #A2B4B6; }}
QPushButton#CompactSettingsToggle:hover, QPushButton#CompactSettingsToggle[expanded="true"] {{ color: #91FF00; border-color: #4B742E; }}
QPushButton#ConverterApply {{ min-height: 38px; background: #25451B; color: #F2F6F4; border-color: #4B742E; font-weight: 750; }}
QPushButton#ConverterApply:hover {{ border-color: #91FF00; color: #91FF00; }}
QPushButton#ConverterApply:disabled {{ background: #172326; color: #697C80; border-color: #25383C; }}
QPushButton#ConverterPrimary {{ min-height: 45px; background: #91FF00; color: #091406; border-color: #91FF00; font-size: 14px; font-weight: 850; }}
QPushButton#ConverterPrimary:hover {{ background: #B8FF50; }}
QPushButton#ConverterPrimary:disabled {{ background: #29421F; color: #71806D; border-color: #29421F; }}
QPushButton#CompactIcon {{ border-radius: 15px; min-width: 30px; min-height: 30px; max-width: 30px; max-height: 30px; padding: 0; background: #0B171A; }}
QPushButton#FooterButton {{ padding: 7px 10px; }}
QCheckBox#BatchCheck::indicator {{ width: 20px; height: 20px; border: 2px solid #82979D; border-radius: 5px; background: #0B171A; }}
QCheckBox#BatchCheck::indicator:checked {{ background: #91FF00; border-color: #91FF00; }}
'''
