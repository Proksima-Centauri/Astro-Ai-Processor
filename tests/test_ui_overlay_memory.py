import os
from pathlib import Path
import subprocess
import sys


def test_large_plate_solve_overlay_is_bounded_and_kept_above_image():
    repo_root = Path(__file__).resolve().parents[1]
    script = r'''
import importlib.util
import json
import os
import sys
import tempfile
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("astro_app_overlay_test", "Astro Ai Processor.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
app = module.QApplication([])
os.environ["GTK_THEME"] = "WhiteSur-Dark"
assert module.is_white_sur_desktop_theme_active()
white_sur_dialog = module.QDialog()
module.apply_dialog_window_flags(white_sur_dialog)
white_sur_flags = white_sur_dialog.windowFlags()
assert white_sur_flags & module.Qt.WindowMinimizeButtonHint
assert white_sur_flags & module.Qt.WindowMaximizeButtonHint
white_sur_dialog.close()

class CanvasFactory:
    _overlay_render_size = staticmethod(module.AstroApp._overlay_render_size)
    _new_overlay_canvas = module.AstroApp._new_overlay_canvas

size = CanvasFactory._overlay_render_size(20000, 12000)
assert max(size) == 4096
assert abs(size[0] / size[1] - 20000 / 12000) < 0.001
canvas, painter = CanvasFactory()._new_overlay_canvas(20000, 12000)
assert (canvas.width(), canvas.height()) == size
painter.end()

viewer = module.BlendViewer()
viewer.set_before(module.QPixmap(1000, 800))
viewer.set_overlay_pixmap(module.QPixmap(100, 80))
item = viewer.view._overlay_item
assert item is not None
assert abs(item.transform().m11() - 10.0) < 1e-9
assert abs(item.transform().m22() - 10.0) < 1e-9
assert item.zValue() > viewer.view._pixmap_item.zValue()
assert item.acceptedMouseButtons() == module.Qt.NoButton
viewer.clear_overlay()
assert viewer.view._overlay_item is None

temporary_home = tempfile.TemporaryDirectory()
os.environ["HOME"] = temporary_home.name
os.environ["XDG_CONFIG_HOME"] = temporary_home.name + "/config"
os.environ["XDG_DATA_HOME"] = temporary_home.name + "/data"
window = module.AstroApp()
assert window.windowTitle() == "Astro AI Processor"
assert window.topbar_splitter.handleWidth() == 5
assert window.topbar_splitter.styleSheet() == ""
assert "QSplitter::handle:vertical" in app.styleSheet()
window.resize(1600, 900)
window.show()
app.processEvents()
with patch.object(module.QFileDialog, "getOpenFileName", return_value=("/tmp/example.fits", "")) as open_dialog, patch.object(window, "load_image_from_path") as image_loader:
    window.load_image()
image_loader.assert_called_once_with("/tmp/example.fits")
assert open_dialog.call_args.args[0] is window
assert open_dialog.call_args.args[1] == "Wybierz obraz"
assert open_dialog.call_args.args[2] == window._get_default_dialog_directory()
assert "Obrazy (*.png" in open_dialog.call_args.args[3]
assert open_dialog.call_args.kwargs == {}
assert window.dashboard_page.layout().count() == 2
assert window.dashboard_sidebar.isVisible()
assert window.dashboard_sidebar.width() == 220
assert window.dashboard_sidebar.height() > 0
assert window.dashboard_search.parentWidget() is window.dashboard_sidebar
assert window.dashboard_title_label.parentWidget().objectName() != "dashboardSidebar"
assert len(window.dashboard_tab_buttons) == 5
assert window.dashboard_stack.count() == 5
assert len(window.dashboard_cards_by_tab["gallery"]) == 10
assert window.dashboard_page.layout().itemAt(1).widget().width() > window.dashboard_sidebar.width()
assert window.dashboard_settings_scroll.isVisible() is False
window._set_dashboard_tab(2)
assert window.dashboard_settings_scroll.isVisible()
assert window.dashboard_cpu_cores.value() == window.processor_cores
assert window.dashboard_onnx_provider.currentText() == window.onnx_provider
assert window.dashboard_api_key.echoMode() == module.QLineEdit.Password
assert window.dashboard_select_models_button.isVisible()
assert window.dashboard_select_starnet_button.isVisible()
assert window.dashboard_select_deepsnr_button.isVisible()
assert window.dashboard_run_deepsnr_button.isVisible()
assert window.dashboard_joystick_button.isVisible()
assert window.dashboard_layers_info.isVisible()
assert window.dashboard_settings_scroll.height() > 600
window.dashboard_cpu_cores.setValue(1)
window.dashboard_onnx_provider.setCurrentText("CPU only")
window.dashboard_api_key.setText("test-openrouter-key")
window.dashboard_save_settings_button.click()
assert window.processor_cores == 1
assert window.onnx_provider == "CPU only"
assert window.openrouter_api_key == "test-openrouter-key"
with open(module.get_config_path(), encoding="utf-8") as config_file:
    saved_settings = json.load(config_file)
assert saved_settings["processor_cores"] == 1
assert saved_settings["onnx_provider"] == "CPU only"
assert saved_settings["openrouter_api_key"] == "test-openrouter-key"
window._set_dashboard_tab(1)
first_gallery_card = window.dashboard_cards_by_tab["gallery"][0]
assert first_gallery_card.parentWidget() is window.gallery_page
assert window.gallery_grid.rowCount() == 2
window._set_dashboard_tab(1)
assert window.dashboard_stack.currentIndex() == 1
assert window.dashboard_tab_buttons[1].isChecked()
window.dashboard_search.setText("Bubble")
assert sum(not card.isHidden() for card in window.dashboard_cards_by_tab["gallery"]) == 5
window.dashboard_search.clear()
window._set_dashboard_tab(3)
assert window.dashboard_stack.currentWidget().findChild(module.AIAssistantPanel) is window.dashboard_altair_chat
assert window.dashboard_page.styleSheet().find("background: #000000") >= 0
assert window.dashboard_sidebar.styleSheet().find("background: #000000") >= 0
assert window.dashboard_content.styleSheet().find("background: #000000") >= 0
assert window.dashboard_tab_buttons[3].styleSheet().find("background: #000000") >= 0
assert window.dashboard_altair_chat.btn_analyze.isHidden()
script_request = "Wygeneruj skrypt, który otworzy obraz M27 i wykona Astro Upscale x2"
assert window.dashboard_altair_chat._is_script_generation_request(script_request)
altair_prompt = module.build_altair_system_prompt()
assert 'astroap.load("M27")' in altair_prompt
assert "nie generuj kodu od razu" not in altair_prompt.lower()
worker_type = module.AltairAIWorker
started_workers = []
class SignalStub:
    def connect(self, _callback):
        pass
class WorkerStub:
    def __init__(self, message, payload, api_key=""):
        self.message = message
        self.payload = payload
        self.api_key = api_key
        self.finished_signal = SignalStub()
        self.chunk_signal = SignalStub()
    def start(self):
        started_workers.append(self)
module.AltairAIWorker = WorkerStub
window.dashboard_altair_chat.get_context_payload = lambda: {}
window.dashboard_altair_chat.input_text.setPlainText(script_request)
window.dashboard_altair_chat.on_send_message()
assert len(started_workers) == 1
assert started_workers[0].message == script_request
assert window.dashboard_altair_chat.file_search_worker is None
module.AltairAIWorker = worker_type
chat_panel = window.dashboard_altair_chat
first_chat_id = chat_panel.current_chat_id
chat_panel.append_assistant_message("M27 will be located automatically.")
assert chat_panel.chat_history_dir == os.path.join(
    temporary_home.name, ".astroaiprocessor", "altair_chats"
)
with open(chat_panel._chat_history_file(first_chat_id), encoding="utf-8") as history_file:
    saved_chat = json.load(history_file)
assert [item["role"] for item in saved_chat["messages"]] == ["User", module.AI_ASSISTANT_NAME]
chat_panel._start_new_chat()
assert chat_panel.current_chat_id != first_chat_id
assert chat_panel.conversation_stack.currentWidget() is chat_panel.welcome_page
chat_panel.chat_history_combo.setCurrentIndex(chat_panel.chat_history_combo.findData(first_chat_id))
assert chat_panel.current_chat_id == first_chat_id
assert chat_panel.current_chat_messages[-1]["content"] == "M27 will be located automatically."
window._set_dashboard_tab(4)
assert window.dashboard_page.styleSheet().find("background: #151a22") >= 0
assert window.dashboard_script_view_stack.currentIndex() == 0
assert len(window.dashboard_script_cards) == 1
new_script_card = window.dashboard_script_cards[0]
assert new_script_card.findChild(module.QLabel, "dashboardCardObject").text() == "New script"
new_script_card.activated.emit("__new_dashboard_script__")
assert window.dashboard_script_view_stack.currentIndex() == 1
assert window.dashboard_script_errors.toPlainText()
window.dashboard_script_back_button.click()
assert window.dashboard_script_view_stack.currentIndex() == 0
generated_script = 'import astroap\nastroap.load("M27")\nastroap.astroupscale(amount=2)'
window.dashboard_altair_chat.script_generated.emit(generated_script)
assert len(window.dashboard_script_cards) == 2
assert window.dashboard_script_view_stack.currentIndex() == 0
script_card = next(card for card in window.dashboard_script_cards if card.image_path.endswith(".py"))
script_card.activated.emit(script_card.image_path)
assert not hasattr(window, "dashboard_script_editor")
assert window.dashboard_script_view_stack.currentIndex() == 1
assert len(window.dashboard_script_blocks) == 2
assert [block["operation"].currentData() for block in window.dashboard_script_blocks] == [
    "load",
    "astroupscale",
]
assert window.dashboard_script_blocks[0]["fields"]["path_or_query"].text() == "M27"
assert window.dashboard_script_blocks[1]["fields"]["amount"].currentData() == 2
assert window.dashboard_script_blocks[0]["frame"].acceptDrops()
window.dashboard_altair_chat.append_assistant_message("**Gotowe**\n\n- Wczytaj M27\n- Zwiększ skalę 2×")
assistant_row = window.dashboard_altair_chat.chat_layout.itemAt(
    window.dashboard_altair_chat.chat_layout.count() - 2
).widget()
assistant_text = next(
    label for label in assistant_row.findChildren(module.QLabel)
    if "<span" in label.text()
)
assert assistant_text is not None
assert assistant_text.textFormat() == module.Qt.RichText
assert "<span" in assistant_text.text() and "font-weight:600" in assistant_text.text()
assert not isinstance(assistant_text.parentWidget(), module.QFrame)
window.dashboard_altair_chat.streaming_response = ""
window.dashboard_altair_chat.streaming_message_label = None
window.dashboard_altair_chat.on_ai_chunk("Altair ")
streaming_label = window.dashboard_altair_chat.streaming_message_label
window.dashboard_altair_chat.on_ai_chunk("**odpowiada**")
assert window.dashboard_altair_chat.streaming_message_label is streaming_label
assert "font-weight:600" in streaming_label.text()
execution_calls = []
original_execute_script = module.astroap.execute_script
module.astroap.execute_script = lambda source: execution_calls.append(source)
window._run_dashboard_script()
assert len(execution_calls) == 1
assert [(call.function, call.args, call.kwargs) for call in module.astroap.validate_script(execution_calls[0])] == [
    ("load", (), {"path_or_query": "M27"}),
    ("astroupscale", (), {"amount": 2}),
]
assert "completed successfully" in window.dashboard_script_output.toPlainText()
window.dashboard_script_blocks[0]["fields"]["path_or_query"].clear()
window._run_dashboard_script()
assert len(execution_calls) == 1
assert "Script failed:" in window.dashboard_script_output.toPlainText()
window.dashboard_script_blocks[0]["fields"]["path_or_query"].setText("M27")
background_block = window._add_dashboard_script_block("bge")
background_block["fields"]["show_dialog"].setChecked(True)
background_block["fields"]["smoothing"].setValue(12.5)
background_call = module.astroap.validate_script(window._dashboard_script_source())[-1]
assert background_call.function == "bge"
assert background_call.kwargs["show_dialog"] is True
assert background_call.kwargs["smoothing"] == 12.5
background_block["frame"].dropped.emit(2, 1)
assert window.dashboard_script_blocks[1] is background_block
window._remove_dashboard_script_block(background_block)
window.dashboard_save_script_button.click()
with open(window.dashboard_script_path, encoding="utf-8") as saved_script_file:
    saved_script = saved_script_file.read()
assert [call.function for call in module.astroap.validate_script(saved_script)] == [
    "load",
    "astroupscale",
]
module.astroap.execute_script = original_execute_script
linear_card = window._dashboard_image_card("tests/fixtures/color16_5x5.tiff")
badge = linear_card.findChild(module.QLabel, "dashboardCardAutostretchBadge")
assert badge is not None and badge.text() == "AutoStretch"
image_frame = linear_card.layout().itemAt(0).widget()
preview_label = image_frame.layout().itemAt(0).widget()
assert preview_label.pixmap() is not None and not preview_label.pixmap().isNull()
nonlinear_path = os.path.join(temporary_home.name, "display.png")
assert module.safe_imwrite(nonlinear_path, module.np.full((8, 8, 3), 127, dtype=module.np.uint8))
_, is_autostretched = window._dashboard_image_pixmap(nonlinear_path)
assert not is_autostretched
assert not window.windowFlags() & module.Qt.FramelessWindowHint
assert not hasattr(window, "whitesur_titlebar")
assert window.menuBar() is not None and not window.menuBar().isVisible()
module.apply_theme_application(app, "Light", "ZWO Red")
assert "background-color: #cfcfcf" in app.styleSheet()
assert "background-color: #d51313" in app.styleSheet()
module.apply_theme_application(app, "Fusion Dark", "Ultra Blue")
ask_icon = window.command_palette_dialog.ask_icon.pixmap()
assert ask_icon is not None and not ask_icon.isNull()
assert ask_icon.toImage().pixelColor(ask_icon.width() // 2, ask_icon.height() // 2).name() == "#007acc"
window.command_palette_dialog.set_accent("ZWO Red")
red_icon = window.command_palette_dialog.ask_icon.pixmap()
assert red_icon is not None
assert red_icon.toImage().pixelColor(red_icon.width() // 2, red_icon.height() // 2).name() == "#d51313"
window.apply_preferences(accent_name="SkyWatcher Green")
green_icon = window.command_palette_dialog.ask_icon.pixmap()
assert green_icon is not None
assert green_icon.toImage().pixelColor(green_icon.width() // 2, green_icon.height() // 2).name() == "#328500"
assert not window.btn_grid_overlay_bottom.isEnabled()
window.latest_plate_solve_result = {"solution": {}}
window._sync_plate_overlay_controls()
assert window.btn_grid_overlay_bottom.isEnabled()
window.btn_grid_overlay_bottom.click()
assert window.layer_visibility["grid_overlay"]
window.btn_object_overlay_bottom.click()
assert window.layer_visibility["object_labels"]
assert window.layer_visibility["plate_solve_overlay"]
assert window.plate_solving_dialog.chk_grid_overlay.isChecked()
assert window.plate_solving_dialog.chk_annotate_overlay.isChecked()
assert window.plate_solving_dialog.spin_grid_scale.value() == 1.0
assert window.plate_solving_dialog.spin_label_scale.value() == 1.0
window.plate_solving_dialog.spin_grid_scale.setValue(1.8)
window.plate_solving_dialog.spin_label_scale.setValue(1.4)
assert abs(window.plate_grid_scale - 1.8) < 1e-9
assert abs(window.plate_label_scale - 1.4) < 1e-9
calls = []
window.run_plate_solve = lambda automatic=False: calls.append(bool(automatic))
window.load_image_from_path("tests/fixtures/color16_5x5.tiff")
app.processEvents()
assert calls == [True]
assert window.menuBar().isVisible()
window.close()
temporary_home.cleanup()
'''
    env = os.environ.copy()
    env["XDG_SESSION_TYPE"] = ""
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
