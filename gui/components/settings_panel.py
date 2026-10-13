"""Settings and Tuning Control Panel for Reelsator."""

import os
from dataclasses import replace
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSlider, QCheckBox, QLineEdit,
    QFileDialog, QButtonGroup, QScrollArea, QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal

from core.smart_cropper import AspectRatio
from core.exif_spoofer import CameraPreset, MetadataMode
from core.insta_optimizer import ProcessingConfig
from core.photo_effects import GrainMode
from core.user_presets import PresetStore, PresetStoreError, recipe_config
from gui.icon_utils import create_header_widget, get_app_icon


class NoWheelSlider(QSlider):
    """QSlider that ignores mouse wheel events to prevent accidental value changes during scrolling."""

    def wheelEvent(self, event):
        event.ignore()


class NoWheelComboBox(QComboBox):
    """QComboBox that ignores mouse wheel events to prevent accidental selection changes during scrolling."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(16)

    def wheelEvent(self, event):
        event.ignore()


class SettingsPanelWidget(QFrame):
    """Configuration panel for tuning Instagram optimization parameters."""

    config_changed = Signal(ProcessingConfig)

    def __init__(self, parent=None, preset_store=None):
        super().__init__(parent)
        self.setObjectName("sidebarPanel")
        self.setMinimumWidth(340)
        self.setMaximumWidth(420)

        self._current_config = ProcessingConfig.ofm_master()
        self._is_updating_ui = False
        self._user_customized_output_dir = False
        self._output_dir = os.path.abspath("./_ready_for_instagram")
        self._photo_controls = {}
        self.preset_store = preset_store if preset_store is not None else PresetStore()
        self._user_presets = {}
        self._store_available = True
        self._profile_name = "OFM Master"
        self._profile_config = recipe_config(self._current_config)
        self._profile_button = None
        self._user_preset_name = None

        self._init_ui()
        self._profile_button = self.btn_preset_ofm
        self._refresh_user_presets()
        self._apply_config_to_ui(self._current_config)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        profile_row = QHBoxLayout()
        self.lbl_profile = QLabel(self)
        self.lbl_profile.setTextFormat(Qt.PlainText)
        self.lbl_profile.setWordWrap(True)
        self.lbl_profile.setStyleSheet("color: #c7d2fe; background: transparent; border: none;")
        self.btn_reset_profile = QPushButton("Сбросить", self)
        self.btn_reset_profile.setToolTip("Вернуть все настройки выбранного пресета.")
        self.btn_reset_profile.clicked.connect(self._reset_profile)
        profile_row.addWidget(self.lbl_profile, 1)
        profile_row.addWidget(self.btn_reset_profile)
        main_layout.addLayout(profile_row)

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
        container.setStyleSheet("QWidget#settingsContainer { background: transparent; border: none; }")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(16)

        # --- Section 1: Presets ---
        hdr_presets = create_header_widget("sparkles", "БЫСТРЫЕ ПРЕСЕТЫ", color="accent", icon_size=16, parent=self)
        layout.addWidget(hdr_presets)

        preset_layout = QVBoxLayout()
        preset_layout.setSpacing(6)

        self.btn_preset_soft_flash = QPushButton(" Soft Flash • мягкая вспышка", self)
        self.btn_preset_soft_flash.setObjectName("pillButton")
        self.btn_preset_soft_flash.setIcon(get_app_icon("camera", "accent", 15))
        self.btn_preset_soft_flash.setCheckable(True)
        self.btn_preset_soft_flash.setToolTip("Тёплые приглушённые цвета, мягкие света и преимущественно яркостное зерно.")

        self.btn_preset_digicam_flash = QPushButton(" Digicam Flash • цветное зерно", self)
        self.btn_preset_digicam_flash.setObjectName("pillButton")
        self.btn_preset_digicam_flash.setIcon(get_app_icon("camera", "accent", 15))
        self.btn_preset_digicam_flash.setCheckable(True)
        self.btn_preset_digicam_flash.setToolTip("Яркая вспышка, выраженные детали и цветное зерно, сохраняющееся после JPEG-сжатия.")

        self.btn_preset_ofm = QPushButton(" OFM Master (Лента 4:5)", self)
        self.btn_preset_ofm.setObjectName("pillButton")
        self.btn_preset_ofm.setIcon(get_app_icon("star", "accent", 15))
        self.btn_preset_ofm.setCheckable(True)
        self.btn_preset_ofm.setChecked(True)

        self.btn_preset_anti = QPushButton(" Микротекстура и детали", self)
        self.btn_preset_anti.setToolTip("Нейтральная микротекстура и локальный контраст ISP.")
        self.btn_preset_anti.setObjectName("pillButton")
        self.btn_preset_anti.setIcon(get_app_icon("cpu", "accent", 15))
        self.btn_preset_anti.setCheckable(True)

        self.btn_preset_natural = QPushButton(" iPhone Natural (Селфи)", self)
        self.btn_preset_natural.setObjectName("pillButton")
        self.btn_preset_natural.setIcon(get_app_icon("smartphone", "accent", 15))
        self.btn_preset_natural.setCheckable(True)

        self.btn_preset_bypass = QPushButton(" Глубокая обработка", self)
        self.btn_preset_bypass.setToolTip("Усиленная оптика, микротекстура и частотные изменения.")
        self.btn_preset_bypass.setObjectName("pillButton")
        self.btn_preset_bypass.setIcon(get_app_icon("flame", "accent", 15))
        self.btn_preset_bypass.setCheckable(True)

        self.btn_preset_story = QPushButton(" Story / Reels (9:16)", self)
        self.btn_preset_story.setObjectName("pillButton")
        self.btn_preset_story.setIcon(get_app_icon("film", "accent", 15))
        self.btn_preset_story.setCheckable(True)

        self.preset_group = QButtonGroup(self)
        self.preset_group.setExclusive(True)
        for b in [
            self.btn_preset_soft_flash, self.btn_preset_digicam_flash,
            self.btn_preset_ofm, self.btn_preset_anti, self.btn_preset_natural,
            self.btn_preset_bypass, self.btn_preset_story,
        ]:
            self.preset_group.addButton(b)
            preset_layout.addWidget(b)

        self.btn_preset_ofm.clicked.connect(lambda: self._select_preset("ofm"))
        self.btn_preset_anti.clicked.connect(lambda: self._select_preset("anti"))
        self.btn_preset_natural.clicked.connect(lambda: self._select_preset("natural"))
        self.btn_preset_bypass.clicked.connect(lambda: self._select_preset("bypass"))
        self.btn_preset_story.clicked.connect(lambda: self._select_preset("story"))
        self.btn_preset_soft_flash.clicked.connect(lambda: self._select_preset("soft_flash"))
        self.btn_preset_digicam_flash.clicked.connect(lambda: self._select_preset("digicam_flash"))

        layout.addLayout(preset_layout)

        layout.addWidget(create_header_widget(
            "star", "МОИ ПРЕСЕТЫ", color="accent", icon_size=16, parent=self,
        ))
        self.combo_user_presets = NoWheelComboBox(self)
        self.combo_user_presets.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.combo_user_presets.setMinimumContentsLength(16)
        self.combo_user_presets.currentIndexChanged.connect(self._on_user_preset_selected)
        layout.addWidget(self.combo_user_presets)
        self.btn_save_preset = QPushButton("Сохранить как…", self)
        self.btn_save_preset.clicked.connect(self._save_user_preset)
        layout.addWidget(self.btn_save_preset)
        user_actions = QHBoxLayout()
        self.btn_update_preset = QPushButton("Обновить", self)
        self.btn_update_preset.setToolTip("Сохранить изменения в выбранном личном пресете.")
        self.btn_update_preset.clicked.connect(self._update_user_preset)
        self.btn_delete_preset = QPushButton("Удалить", self)
        self.btn_delete_preset.clicked.connect(self._delete_user_preset)
        user_actions.addWidget(self.btn_update_preset)
        user_actions.addWidget(self.btn_delete_preset)
        layout.addLayout(user_actions)
        self.lbl_preset_message = QLabel(self)
        self.lbl_preset_message.setTextFormat(Qt.PlainText)
        self.lbl_preset_message.setWordWrap(True)
        self.lbl_preset_message.hide()
        layout.addWidget(self.lbl_preset_message)

        # --- Section 2: Format & Framing ---
        hdr_format = create_header_widget("crop", "ФОРМАТ И КАДРИРОВАНИЕ", color="accent", icon_size=16, parent=self)
        layout.addWidget(hdr_format)

        self.combo_aspect = NoWheelComboBox(self)
        self.combo_aspect.addItem("4:5 • Лента (1080 × 1350)", AspectRatio.FEED_4_5)
        self.combo_aspect.addItem("1:1 • Квадрат (1080 × 1080)", AspectRatio.SQUARE_1_1)
        self.combo_aspect.addItem("9:16 • Stories / Reels (1080 × 1920)", AspectRatio.STORY_9_16)
        self.combo_aspect.addItem("Оригинальные пропорции (до 4096 px)", AspectRatio.ORIGINAL)
        self.combo_aspect.currentIndexChanged.connect(self._on_ui_changed)
        layout.addWidget(self.combo_aspect)

        self.chk_face_detect = QCheckBox("Центрировать по лицу", self)
        self.chk_face_detect.setChecked(True)
        self.chk_face_detect.toggled.connect(self._on_ui_changed)
        layout.addWidget(self.chk_face_detect)

        # --- Section 3: Camera Emulation (EXIF) ---
        hdr_camera = create_header_widget("camera", "МЕТАДАННЫЕ EXIF", color="accent", icon_size=16, parent=self)
        layout.addWidget(hdr_camera)

        self.combo_metadata = NoWheelComboBox(self)
        self.combo_metadata.addItem("Без EXIF (полная очистка)", MetadataMode.NO_EXIF)
        self.combo_metadata.addItem("Минимальные (sRGB)", MetadataMode.MINIMAL)
        self.combo_metadata.addItem("Профиль камеры (синтетический)", MetadataMode.SYNTHETIC_CAMERA)
        self.combo_metadata.setToolTip("Профиль камеры добавляет вымышленные данные съёмки. Минимальный режим сохраняет технический EXIF sRGB.")
        self.combo_metadata.currentIndexChanged.connect(self._on_ui_changed)
        layout.addWidget(self.combo_metadata)

        self.combo_camera = NoWheelComboBox(self)
        self.combo_camera.addItem("Apple iPhone 15 Pro", CameraPreset.IPHONE_15_PRO)
        self.combo_camera.addItem("Apple iPhone 16 Pro Max", CameraPreset.IPHONE_16_PRO_MAX)
        self.combo_camera.addItem("Sony A7 IV", CameraPreset.SONY_A7_IV)
        self.combo_camera.currentIndexChanged.connect(self._on_ui_changed)
        layout.addWidget(self.combo_camera)

        layout.addWidget(create_header_widget(
            "sliders-horizontal", "СВЕТ И ЦВЕТ", color="accent", icon_size=16, parent=self,
        ))
        self._add_photo_controls(layout, (
            ("exposure_ev", "Экспозиция:", -300, 300, 100, "{:+.2f} EV"),
            ("temperature", "Температура (холоднее / теплее):", -100, 100, 100, "{:+.0%}"),
            ("tint", "Оттенок (зелёный / пурпурный):", -100, 100, 100, "{:+.0%}"),
            ("saturation", "Насыщенность:", 0, 200, 100, "{:.0%}"),
            ("tone_contrast", "S-кривая (контраст):", -100, 100, 100, "{:+.0%}"),
            ("black_lift", "Подъём чёрного:", 0, 150, 1000, "{:.1%}"),
            ("highlight_rolloff", "Смягчение светов:", 0, 100, 100, "{:.0%}"),
            ("bloom_strength", "Свечение светов:", 0, 100, 100, "{:.0%}"),
            ("bloom_radius_px", "Радиус свечения:", 1, 60, 1, "{:.0f} px"),
        ))

        # --- Optics & Frequency Sliders ---
        hdr_optics = create_header_widget("sliders-horizontal", "ДЕТАЛИ И ОПТИКА", color="accent", icon_size=16, parent=self)
        layout.addWidget(hdr_optics)

        # Chromatic Aberration (Хроматические аберрации)
        self.slider_aberration, self.val_aberration = self._create_slider_row(
            layout, "Хроматические аберрации:", 0, 200, 65, "0.65 px"
        )
        self.slider_aberration.valueChanged.connect(self._on_ui_changed)

        # Vignette (Оптическая виньетка)
        self.slider_vignette, self.val_vignette = self._create_slider_row(
            layout, "Оптическая виньетка:", 0, 60, 25, "2.5%"
        )
        self.slider_vignette.valueChanged.connect(self._on_ui_changed)

        # Frequency / Jitter Disruption
        self.slider_disrupt, self.val_disrupt = self._create_slider_row(
            layout, "Частотные изменения:", 0, 200, 100, "1.00x"
        )
        self.slider_disrupt.valueChanged.connect(self._on_ui_changed)

        # Apple Photonic Engine Color Grade
        self.chk_photonic = QCheckBox("Тональная калибровка Apple Photonic", self)
        self.chk_photonic.setChecked(True)
        self.chk_photonic.toggled.connect(self._on_ui_changed)
        layout.addWidget(self.chk_photonic)

        # Neutral microtexture (legacy Bayer configuration flag)
        self.chk_bayer = QCheckBox("Нейтральная микротекстура", self)
        self.chk_bayer.setToolTip("Добавляет мелкую текстуру яркости, сохраняя цветовой баланс изображения.")
        self.chk_bayer.setChecked(False)
        self.chk_bayer.toggled.connect(self._on_ui_changed)
        layout.addWidget(self.chk_bayer)
        self._add_photo_controls(layout, (
            ("bayer_strength", "Сила микротекстуры:", 0, 200, 100, "{:.2f}"),
        ))

        # ISP Local Contrast
        self.chk_isp = QCheckBox("Усилить детали (ISP)", self)
        self.chk_isp.setToolTip("Усиливает мелкие детали и локальный контраст; чрезмерная сила может создавать ореолы.")
        self.chk_isp.setChecked(False)
        self.chk_isp.toggled.connect(self._on_ui_changed)
        layout.addWidget(self.chk_isp)
        self._add_photo_controls(layout, (
            ("sharpen_amount", "Сила усиления деталей:", 0, 200, 100, "{:.2f}"),
        ))

        layout.addWidget(create_header_widget(
            "sliders-horizontal", "ЗЕРНО", color="accent", icon_size=16, parent=self,
        ))
        self.combo_grain_mode = NoWheelComboBox(self)
        self.combo_grain_mode.addItem("Сенсорное зерно", GrainMode.SENSOR)
        self.combo_grain_mode.addItem("Художественное зерно", GrainMode.FILM)
        self.combo_grain_mode.currentIndexChanged.connect(self._on_ui_changed)
        layout.addWidget(self.combo_grain_mode)
        self.slider_grain, self.val_grain = self._create_slider_row(
            layout, "Сила сенсорного зерна:", 0, 200, 100, "1.00x"
        )
        self.slider_grain.valueChanged.connect(self._on_ui_changed)
        self._add_photo_controls(layout, (
            ("luma_grain_strength", "Яркостное зерно:", 0, 120, 10, "{:.1f}"),
            ("chroma_grain_strength", "Цветное зерно:", 0, 240, 10, "{:.1f}"),
            ("grain_size_px", "Размер зерна:", 10, 40, 10, "{:.1f} px"),
        ))
        self._photo_controls["chroma_grain_strength"][0].setToolTip(
            "Цветной шум сглаживается JPEG-сжатием. Проверяйте результат в режиме «100% / После JPEG»."
        )
        self._photo_controls["bloom_radius_px"][0].setToolTip("Радиус в пикселях итогового кадра; действует при включённом свечении.")

        self.slider_jpeg, self.val_jpeg = self._create_slider_row(
            layout, "Качество JPEG:", 1, 100, 90, "90"
        )
        self.slider_jpeg.valueChanged.connect(self._on_ui_changed)

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

    def _add_photo_controls(self, layout, specs):
        for field, label, lower, upper, scale, fmt in specs:
            value = getattr(self._current_config, field)
            slider, value_label = self._create_slider_row(
                layout, label, lower, upper, int(round(value * scale)), fmt.format(value),
            )
            self._photo_controls[field] = (slider, value_label, scale, fmt)
            slider.valueChanged.connect(self._on_ui_changed)

    def _update_grain_controls(self, mode):
        film = mode == GrainMode.FILM
        self.slider_grain.setEnabled(not film)
        self.val_grain.setEnabled(not film)
        for field in ("luma_grain_strength", "chroma_grain_strength", "grain_size_px"):
            slider, value_label, _, _ = self._photo_controls[field]
            slider.setEnabled(film)
            value_label.setEnabled(film)

    def _update_effect_controls(self):
        for field, enabled in (
            ("bayer_strength", self.chk_bayer.isChecked()),
            ("sharpen_amount", self.chk_isp.isChecked()),
            ("bloom_radius_px", self._photo_controls["bloom_strength"][0].value() > 0),
        ):
            slider, label, _, _ = self._photo_controls[field]
            slider.setEnabled(enabled)
            label.setEnabled(enabled)

    def _create_slider_row(self, parent_layout, label_text, min_v, max_v, default_v, default_str):
        row = QHBoxLayout()
        lbl = QLabel(label_text, self)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size: 12px; color: #9ca3af; background: transparent; border: none;")
        val_lbl = QLabel(default_str, self)
        val_lbl.setObjectName("valueLabel")
        val_lbl.setStyleSheet("background: transparent; border: none;")
        val_lbl.setAlignment(Qt.AlignRight)

        row.addWidget(lbl, 1)
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
        presets = {
            "soft_flash": (ProcessingConfig.soft_flash, self.btn_preset_soft_flash),
            "digicam_flash": (ProcessingConfig.digicam_flash, self.btn_preset_digicam_flash),
            "ofm": (ProcessingConfig.ofm_master, self.btn_preset_ofm),
            "anti": (ProcessingConfig.anti_classifier, self.btn_preset_anti),
            "natural": (ProcessingConfig.iphone_natural, self.btn_preset_natural),
            "bypass": (ProcessingConfig.aggressive_bypass, self.btn_preset_bypass),
            "story": (ProcessingConfig.story_reels, self.btn_preset_story),
        }
        if preset_name not in presets:
            return
        factory, button = presets[preset_name]
        cfg = factory()
        names = {
            "soft_flash": "Soft Flash", "digicam_flash": "Digicam Flash", "ofm": "OFM Master",
            "anti": "Микротекстура и детали", "natural": "iPhone Natural",
            "bypass": "Глубокая обработка", "story": "Story / Reels",
        }
        self.combo_user_presets.blockSignals(True)
        self.combo_user_presets.setCurrentIndex(0)
        self.combo_user_presets.blockSignals(False)
        self._set_profile(cfg, names[preset_name], button=button)
        self.config_changed.emit(cfg)

    def _set_profile(self, cfg, name, button=None, user_name=None):
        self._profile_name = name
        self._profile_config = recipe_config(cfg)
        self._profile_button = button
        self._user_preset_name = user_name
        self._apply_config_to_ui(cfg)

    def _update_profile_state(self):
        modified = recipe_config(self._current_config) != self._profile_config
        self.lbl_profile.setText(self._profile_name + (" • изменён" if modified else ""))
        self.btn_reset_profile.setEnabled(modified)
        self.preset_group.setExclusive(False)
        for button in self.preset_group.buttons():
            button.setChecked(button is self._profile_button and not modified)
        self.preset_group.setExclusive(True)
        personal = self._user_preset_name in self._user_presets
        self.btn_save_preset.setEnabled(self._store_available)
        self.btn_update_preset.setEnabled(self._store_available and personal and modified)
        self.btn_delete_preset.setEnabled(self._store_available and personal)

    def _reset_profile(self):
        # Keep explicitly configured session settings while restoring the recipe.
        current = self._current_config
        restored = replace(self._profile_config, random_seed=current.random_seed,
                           capture_time=current.capture_time, overwrite_existing=current.overwrite_existing)
        self._apply_config_to_ui(restored)
        self.config_changed.emit(restored)

    def _preset_message(self, message, error=False):
        self.lbl_preset_message.setText(message)
        self.lbl_preset_message.setStyleSheet(
            f"color: {'#fca5a5' if error else '#a5b4fc'}; background: transparent; border: none; font-size: 12px;"
        )
        self.lbl_preset_message.setToolTip(str(self.preset_store.path))
        self.lbl_preset_message.setVisible(bool(message))

    def _refresh_user_presets(self, selected=None):
        try:
            self._user_presets = self.preset_store.read()
            self._store_available = True
        except PresetStoreError as exc:
            self._user_presets = {}
            self._store_available = False
            self._preset_message(str(exc), error=True)
        self.combo_user_presets.blockSignals(True)
        self.combo_user_presets.clear()
        self.combo_user_presets.addItem("Выберите личный пресет" if self._user_presets else "Нет личных пресетов", None)
        self.combo_user_presets.model().item(0).setEnabled(False)
        for name in sorted(self._user_presets, key=str.casefold):
            self.combo_user_presets.addItem(name, name)
        index = self.combo_user_presets.findData(selected) if selected else 0
        self.combo_user_presets.setCurrentIndex(max(0, index))
        self.combo_user_presets.blockSignals(False)
        self.combo_user_presets.setEnabled(self._store_available and bool(self._user_presets))
        self._update_profile_state()

    def _on_user_preset_selected(self, _index):
        name = self.combo_user_presets.currentData()
        if name not in self._user_presets:
            return
        cfg = replace(self._user_presets[name])
        self._set_profile(cfg, name, user_name=name)
        self._preset_message("")
        self.config_changed.emit(cfg)

    def _save_user_preset(self):
        name, accepted = QInputDialog.getText(self, "Сохранить пресет", "Название:")
        if not accepted:
            return
        try:
            name = self.preset_store.save(name, self._current_config)
            self._refresh_user_presets(selected=name)
            self._on_user_preset_selected(self.combo_user_presets.currentIndex())
            self._preset_message("Пресет сохранён.")
        except PresetStoreError as exc:
            self._preset_message(str(exc), error=True)

    def _update_user_preset(self):
        if self._user_preset_name not in self._user_presets:
            return
        try:
            name = self.preset_store.save(self._user_preset_name, self._current_config, overwrite=True)
            self._refresh_user_presets(selected=name)
            self._on_user_preset_selected(self.combo_user_presets.currentIndex())
            self._preset_message("Изменения сохранены.")
        except PresetStoreError as exc:
            self._preset_message(str(exc), error=True)

    def _delete_user_preset(self):
        name = self._user_preset_name
        if name not in self._user_presets:
            return
        answer = QMessageBox.question(self, "Удалить пресет", f"Удалить «{name}»?",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        try:
            self.preset_store.delete(name)
            self._set_profile(self._current_config, "Свои настройки")
            self._refresh_user_presets()
            self._preset_message("Пресет удалён. Текущие настройки сохранены в панели.")
        except PresetStoreError as exc:
            self._preset_message(str(exc), error=True)

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

        self.slider_jpeg.setValue(cfg.jpeg_quality)
        self.val_jpeg.setText(str(cfg.jpeg_quality))

        for field, (slider, value_label, scale, fmt) in self._photo_controls.items():
            value = getattr(cfg, field)
            slider.setValue(int(round(value * scale)))
            value_label.setText(fmt.format(value))
        self.combo_grain_mode.setCurrentIndex(self.combo_grain_mode.findData(cfg.grain_mode))
        self._update_grain_controls(cfg.grain_mode)
        self._update_effect_controls()
        self._update_profile_state()

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

        selected_meta_mode = MetadataMode(self.combo_metadata.currentData())
        jpeg_quality = self.slider_jpeg.value()
        self.val_jpeg.setText(str(jpeg_quality))
        self.combo_camera.setEnabled(selected_meta_mode == MetadataMode.SYNTHETIC_CAMERA)

        photo_values = {}
        for field, (slider, value_label, scale, fmt) in self._photo_controls.items():
            value = slider.value() / scale
            photo_values[field] = value
            value_label.setText(fmt.format(value))
        grain_mode = GrainMode(self.combo_grain_mode.currentData())
        self._update_grain_controls(grain_mode)
        self._update_effect_controls()

        cfg = replace(
            self._current_config,
            aspect_ratio=AspectRatio(self.combo_aspect.currentData()),
            camera_preset=CameraPreset(self.combo_camera.currentData()),
            metadata_mode=selected_meta_mode,
            disrupt_strength=disrupt_f,
            grain_strength=grain_f,
            aberration_px=aberration_f,
            vignette_strength=vignette_f,
            enable_photonic_grade=self.chk_photonic.isChecked(),
            use_smart_face_centering=self.chk_face_detect.isChecked(),
            enable_bayer_matrix=self.chk_bayer.isChecked(),
            enable_isp_enhancement=self.chk_isp.isChecked(),
            jpeg_quality=jpeg_quality,
            grain_mode=grain_mode,
            **photo_values,
        )
        self._current_config = cfg
        self._update_profile_state()
        self.config_changed.emit(cfg)

    def get_current_config(self) -> ProcessingConfig:
        return self._current_config

    def set_config(self, cfg: ProcessingConfig):
        """Updates UI controls with the specified ProcessingConfig."""
        self.combo_user_presets.blockSignals(True)
        self.combo_user_presets.setCurrentIndex(0)
        self.combo_user_presets.blockSignals(False)
        self._set_profile(cfg, "Свои настройки")
        self.config_changed.emit(cfg)
