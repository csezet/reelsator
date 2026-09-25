"""Settings and Tuning Control Panel for Reelsator."""

import os
from dataclasses import replace
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSlider, QCheckBox, QLineEdit,
    QFileDialog, QButtonGroup, QScrollArea
)
from PySide6.QtCore import Qt, Signal

from core.smart_cropper import AspectRatio
from core.exif_spoofer import CameraPreset, MetadataMode
from core.insta_optimizer import ProcessingConfig
from gui.icon_utils import create_header_widget, get_app_icon


class NoWheelSlider(QSlider):
    """QSlider that ignores mouse wheel events to prevent accidental value changes during scrolling."""

    def wheelEvent(self, event):
        event.ignore()


class NoWheelComboBox(QComboBox):
    """QComboBox that ignores mouse wheel events to prevent accidental selection changes during scrolling."""

    def wheelEvent(self, event):
        event.ignore()


class SettingsPanelWidget(QFrame):
    """Configuration panel for tuning Instagram optimization parameters."""

    config_changed = Signal(ProcessingConfig)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebarPanel")
        self.setMinimumWidth(340)
        self.setMaximumWidth(420)

        self._current_config = ProcessingConfig.ofm_master()
        self._is_updating_ui = False
        self._user_customized_output_dir = False
        self._output_dir = os.path.abspath("./_ready_for_instagram")

        self._init_ui()
        self._apply_config_to_ui(self._current_config)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        # Scroll Area for clean overflow handling with Windows 11 Fluent scrollbar
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 6px;
                margin: 4px 1px 4px 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.18);
                min-height: 36px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(99, 102, 241, 0.7);
            }
            QScrollBar::handle:vertical:pressed {
                background: #6366f1;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                border: none;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        container = QWidget()
        container.setObjectName("settingsContainer")
        container.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(16)

        # --- Section 1: Presets ---
        hdr_presets = create_header_widget("sparkles", "БЫСТРЫЕ ПРЕСЕТЫ", color="accent", icon_size=16, parent=self)
        layout.addWidget(hdr_presets)

        preset_layout = QVBoxLayout()
        preset_layout.setSpacing(6)

        self.btn_preset_ofm = QPushButton(" OFM Master (Лента 4:5)", self)
        self.btn_preset_ofm.setObjectName("pillButton")
        self.btn_preset_ofm.setIcon(get_app_icon("star", "accent", 15))
        self.btn_preset_ofm.setCheckable(True)
        self.btn_preset_ofm.setChecked(True)

        self.btn_preset_anti = QPushButton(" Текстурирование матрицы (ISP & Bayer)", self)
        self.btn_preset_anti.setObjectName("pillButton")
        self.btn_preset_anti.setIcon(get_app_icon("cpu", "accent", 15))
        self.btn_preset_anti.setCheckable(True)

        self.btn_preset_natural = QPushButton(" iPhone Natural (Селфи)", self)
        self.btn_preset_natural.setObjectName("pillButton")
        self.btn_preset_natural.setIcon(get_app_icon("smartphone", "accent", 15))
        self.btn_preset_natural.setCheckable(True)

        self.btn_preset_bypass = QPushButton(" Глубокая обработка (Strong Processing)", self)
        self.btn_preset_bypass.setObjectName("pillButton")
        self.btn_preset_bypass.setIcon(get_app_icon("flame", "accent", 15))
        self.btn_preset_bypass.setCheckable(True)

        self.btn_preset_story = QPushButton(" Story / Reels (9:16)", self)
        self.btn_preset_story.setObjectName("pillButton")
        self.btn_preset_story.setIcon(get_app_icon("film", "accent", 15))
        self.btn_preset_story.setCheckable(True)

        self.preset_group = QButtonGroup(self)
        self.preset_group.setExclusive(True)
        for b in [self.btn_preset_ofm, self.btn_preset_anti, self.btn_preset_natural, self.btn_preset_bypass, self.btn_preset_story]:
            self.preset_group.addButton(b)
            preset_layout.addWidget(b)

        self.btn_preset_ofm.clicked.connect(lambda: self._select_preset("ofm"))
        self.btn_preset_anti.clicked.connect(lambda: self._select_preset("anti"))
        self.btn_preset_natural.clicked.connect(lambda: self._select_preset("natural"))
        self.btn_preset_bypass.clicked.connect(lambda: self._select_preset("bypass"))
        self.btn_preset_story.clicked.connect(lambda: self._select_preset("story"))

        layout.addLayout(preset_layout)

        # --- Section 2: Format & Framing ---
        hdr_format = create_header_widget("crop", "ФОРМАТ И КАДРИРОВАНИЕ", color="accent", icon_size=16, parent=self)
        layout.addWidget(hdr_format)

        self.combo_aspect = NoWheelComboBox(self)
        self.combo_aspect.addItem("4:5 (1080x1350) • Instagram Feed (Топ)", AspectRatio.FEED_4_5)
        self.combo_aspect.addItem("1:1 (1080x1080) • Квадрат", AspectRatio.SQUARE_1_1)
        self.combo_aspect.addItem("9:16 (1080x1920) • Stories / Reels", AspectRatio.STORY_9_16)
        self.combo_aspect.addItem("Оригинальные пропорции (до 4096 px)", AspectRatio.ORIGINAL)
        self.combo_aspect.currentIndexChanged.connect(self._on_ui_changed)
        layout.addWidget(self.combo_aspect)

        self.chk_face_detect = QCheckBox("Умное центрирование лица (OpenCV)", self)
        self.chk_face_detect.setChecked(True)
        self.chk_face_detect.toggled.connect(self._on_ui_changed)
        layout.addWidget(self.chk_face_detect)

        # --- Section 3: Camera Emulation (EXIF) ---
        hdr_camera = create_header_widget("camera", "ЭМУЛЯЦИЯ КАМЕРЫ И EXIF", color="accent", icon_size=16, parent=self)
        layout.addWidget(hdr_camera)

        self.combo_metadata = NoWheelComboBox(self)
        self.combo_metadata.addItem("Без EXIF (полная очистка)", MetadataMode.NO_EXIF)
        self.combo_metadata.addItem("Minimal (sRGB / без фейковых дат)", MetadataMode.MINIMAL)
        self.combo_metadata.addItem("Synthetic Camera (Apple iPhone / Sony)", MetadataMode.SYNTHETIC_CAMERA)
        self.combo_metadata.currentIndexChanged.connect(self._on_ui_changed)
        layout.addWidget(self.combo_metadata)

        self.combo_camera = NoWheelComboBox(self)
        self.combo_camera.addItem("Apple iPhone 15 Pro (f/1.78, 24mm)", CameraPreset.IPHONE_15_PRO)
        self.combo_camera.addItem("Apple iPhone 16 Pro Max (f/1.78, 24mm)", CameraPreset.IPHONE_16_PRO_MAX)
        self.combo_camera.addItem("Sony A7 IV (f/2.8, 35mm GM)", CameraPreset.SONY_A7_IV)
        self.combo_camera.currentIndexChanged.connect(self._on_ui_changed)
        layout.addWidget(self.combo_camera)

        # --- Section 4: Optics & Frequency Sliders ---
        hdr_optics = create_header_widget("sliders-horizontal", "ТОНКАЯ НАСТРОЙКА РЕАЛИЗМА И ОПТИКИ", color="accent", icon_size=16, parent=self)
        layout.addWidget(hdr_optics)

        # Sensor Grain (Шум сенсора)
        self.slider_grain, self.val_grain = self._create_slider_row(
            layout, "Шум сенсора матрицы (ISO Grain):", 0, 200, 100, "1.00x"
        )
        self.slider_grain.valueChanged.connect(self._on_ui_changed)

        # Chromatic Aberration (Хроматические аберрации)
        self.slider_aberration, self.val_aberration = self._create_slider_row(
            layout, "Хроматические аберрации (Линзы):", 0, 200, 65, "0.65 px"
        )
        self.slider_aberration.valueChanged.connect(self._on_ui_changed)

        # Vignette (Оптическая виньетка)
        self.slider_vignette, self.val_vignette = self._create_slider_row(
            layout, "Оптическая виньетка:", 0, 60, 25, "2.5%"
        )
        self.slider_vignette.valueChanged.connect(self._on_ui_changed)

        # Frequency / Jitter Disruption
        self.slider_disrupt, self.val_disrupt = self._create_slider_row(
            layout, "Частотное возмущение пикселей (Frequency Jitter):", 0, 200, 100, "1.00x"
        )
        self.slider_disrupt.valueChanged.connect(self._on_ui_changed)

        # Apple Photonic Engine Color Grade
        self.chk_photonic = QCheckBox("Тональная калибровка Apple Photonic", self)
        self.chk_photonic.setChecked(True)
        self.chk_photonic.toggled.connect(self._on_ui_changed)
        layout.addWidget(self.chk_photonic)

        # Bayer Matrix Sensor Grid
        self.chk_bayer = QCheckBox("Сетка матрицы Байера (Bayer CFA)", self)
        self.chk_bayer.setChecked(False)
        self.chk_bayer.toggled.connect(self._on_ui_changed)
        layout.addWidget(self.chk_bayer)

        # ISP Local Contrast
        self.chk_isp = QCheckBox("Адаптивный контраст ISP (разрушение гладкости ИИ)", self)
        self.chk_isp.setChecked(False)
        self.chk_isp.toggled.connect(self._on_ui_changed)
        layout.addWidget(self.chk_isp)

        # --- Section 5: Output Folder ---
        hdr_out = create_header_widget("folder", "ПАПКА СОХРАНЕНИЯ", color="accent", icon_size=16, parent=self)
        layout.addWidget(hdr_out)

        out_row = QHBoxLayout()
        self.txt_output_dir = QLineEdit(self._output_dir, self)
        self.txt_output_dir.setStyleSheet("background-color: #242632; border: 1px solid #323544; border-radius: 6px; padding: 6px; color: #f3f4f6;")
        self.txt_output_dir.textEdited.connect(self._on_output_dir_edited)
        btn_browse = QPushButton(" Обзор...", self)
        btn_browse.setIcon(get_app_icon("folder-open", "muted", 14))
        btn_browse.clicked.connect(self._choose_output_dir)

        out_row.addWidget(self.txt_output_dir)
        out_row.addWidget(btn_browse)
        layout.addLayout(out_row)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _create_slider_row(self, parent_layout, label_text, min_v, max_v, default_v, default_str):
        row = QHBoxLayout()
        lbl = QLabel(label_text, self)
        lbl.setStyleSheet("font-size: 12px; color: #9ca3af; background: transparent; border: none;")
        val_lbl = QLabel(default_str, self)
        val_lbl.setObjectName("valueLabel")
        val_lbl.setStyleSheet("background: transparent; border: none;")
        val_lbl.setAlignment(Qt.AlignRight)

        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(val_lbl)
        parent_layout.addLayout(row)

        slider = NoWheelSlider(Qt.Horizontal, self)
        slider.setRange(min_v, max_v)
        slider.setValue(default_v)
        parent_layout.addWidget(slider)
        return slider, val_lbl

    def _on_output_dir_edited(self, text: str):
        self._user_customized_output_dir = True
        self._output_dir = text.strip()

    def _choose_output_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку для сохранения готовых фото", self._output_dir)
        if folder:
            self._user_customized_output_dir = True
            self._output_dir = folder
            self.txt_output_dir.setText(folder)

    def get_output_dir(self) -> str:
        return self.txt_output_dir.text().strip()

    def set_output_dir(self, dir_path: str, force: bool = False):
        if not force and self._user_customized_output_dir:
            return
        self._output_dir = dir_path
        self.txt_output_dir.setText(dir_path)

    def has_user_customized_output_dir(self) -> bool:
        return self._user_customized_output_dir

    def _select_preset(self, preset_name: str):
        if preset_name == "ofm":
            cfg = ProcessingConfig.ofm_master()
        elif preset_name == "anti":
            cfg = ProcessingConfig.anti_classifier()
        elif preset_name == "natural":
            cfg = ProcessingConfig.iphone_natural()
        elif preset_name == "bypass":
            cfg = ProcessingConfig.aggressive_bypass()
        elif preset_name == "story":
            cfg = ProcessingConfig.story_reels()
        else:
            return

        self._apply_config_to_ui(cfg)
        self.config_changed.emit(cfg)

    def _apply_config_to_ui(self, cfg: ProcessingConfig):
        self._is_updating_ui = True
        self._current_config = cfg

        # Aspect
        idx = self.combo_aspect.findData(cfg.aspect_ratio)
        if idx >= 0:
            self.combo_aspect.setCurrentIndex(idx)

        # Metadata mode
        idx_m = self.combo_metadata.findData(cfg.metadata_mode)
        if idx_m >= 0:
            self.combo_metadata.setCurrentIndex(idx_m)
        self.combo_camera.setEnabled(cfg.metadata_mode == MetadataMode.SYNTHETIC_CAMERA)

        # Camera
        idx_c = self.combo_camera.findData(cfg.camera_preset)
        if idx_c >= 0:
            self.combo_camera.setCurrentIndex(idx_c)

        self.chk_face_detect.setChecked(cfg.use_smart_face_centering)
        self.chk_photonic.setChecked(cfg.enable_photonic_grade)
        self.chk_bayer.setChecked(cfg.enable_bayer_matrix)
        self.chk_isp.setChecked(cfg.enable_isp_enhancement)

        # Sliders
        self.slider_grain.setValue(int(round(cfg.grain_strength * 100)))
        self.val_grain.setText(f"{cfg.grain_strength:.2f}x")

        self.slider_aberration.setValue(int(round(cfg.aberration_px * 100)))
        self.val_aberration.setText(f"{cfg.aberration_px:.2f} px")

        self.slider_vignette.setValue(int(round(cfg.vignette_strength * 1000)))
        self.val_vignette.setText(f"{cfg.vignette_strength * 100:.1f}%")

        self.slider_disrupt.setValue(int(round(cfg.disrupt_strength * 100)))
        self.val_disrupt.setText(f"{cfg.disrupt_strength:.2f}x")

        self._is_updating_ui = False

    def _on_ui_changed(self):
        if self._is_updating_ui:
            return

        grain_f = self.slider_grain.value() / 100.0
        self.val_grain.setText(f"{grain_f:.2f}x")

        aberration_f = self.slider_aberration.value() / 100.0
        self.val_aberration.setText(f"{aberration_f:.2f} px")

        vignette_f = self.slider_vignette.value() / 1000.0
        self.val_vignette.setText(f"{vignette_f * 100:.1f}%")

        disrupt_f = self.slider_disrupt.value() / 100.0
        self.val_disrupt.setText(f"{disrupt_f:.2f}x")

        selected_meta_mode = self.combo_metadata.currentData()
        self.combo_camera.setEnabled(selected_meta_mode == MetadataMode.SYNTHETIC_CAMERA)

        cfg = replace(
            self._current_config,
            aspect_ratio=self.combo_aspect.currentData(),
            camera_preset=self.combo_camera.currentData(),
            metadata_mode=selected_meta_mode,
            disrupt_strength=disrupt_f,
            grain_strength=grain_f,
            aberration_px=aberration_f,
            vignette_strength=vignette_f,
            enable_photonic_grade=self.chk_photonic.isChecked(),
            use_smart_face_centering=self.chk_face_detect.isChecked(),
            enable_bayer_matrix=self.chk_bayer.isChecked(),
            bayer_strength=1.0 if self.chk_bayer.isChecked() else 0.0,
            enable_isp_enhancement=self.chk_isp.isChecked(),
            sharpen_amount=0.55 if self.chk_isp.isChecked() else 0.0,
        )
        self._current_config = cfg
        self.config_changed.emit(cfg)

    def get_current_config(self) -> ProcessingConfig:
        return self._current_config

    def set_config(self, cfg: ProcessingConfig):
        """Updates UI controls with the specified ProcessingConfig."""
        self._apply_config_to_ui(cfg)
        self.config_changed.emit(cfg)
