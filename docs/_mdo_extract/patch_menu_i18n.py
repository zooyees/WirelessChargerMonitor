from pathlib import Path

path = Path('wireless_charger_monitor/apps/tektronix_scope/panel.py')
text = path.read_text(encoding='utf-8')
start = text.index('    def _on_menu(self, key: str) -> None:')
end = text.index('    def _build_simple_menu(self, title: str, actions: list[tuple[str, str]]):')

new = '''    def _on_menu(self, key: str) -> None:
        self._open_side_menu_key = key
        builders = {
            'acquire': self._build_acquire_menu,
            'trigger': self._build_trigger_menu,
            'measure': self._build_simple_menu(tr('tool.tektronix_scope.side_measure'), [
                ('MEASUrement:MEAS1:STATE ON', _L('打开测量 1', 'Enable Meas 1')),
                ('MEASUrement:MEAS1:TYPe FREQuency', _L('类型: 频率', 'Type: Frequency')),
                ('MEASUrement:MEAS1:TYPe PK2Pk', _L('类型: 峰峰值', 'Type: Peak-Peak')),
                ('MEASUrement:MEAS1:TYPe MEAN', _L('类型: 均值', 'Type: Mean')),
                ('MEASUrement:MEAS1:SOUrce1 CH1', _L('源: CH1', 'Source: CH1')),
            ]),
            'search': self._build_simple_menu(tr('tool.tektronix_scope.side_search'), [
                ('SEARCH:SEARCH1:STATE ON', _L('打开搜索 1', 'Enable Search 1')),
                ('SEARCH:SEARCH1:STATE OFF', _L('关闭搜索 1', 'Disable Search 1')),
            ]),
            'math': self._build_simple_menu(tr('tool.tektronix_scope.side_math'), [
                ('SELect:MATH ON', _L('显示 MATH', 'Show MATH')),
                ('SELect:MATH OFF', _L('关闭 MATH', 'Hide MATH')),
                ('MATH:TYPe DUAL', _L('类型: 双波形', 'Type: Dual')),
                ('MATH:DEFine "CH1-CH2"', 'CH1-CH2'),
                ('MATH:DEFine "CH1*CH2"', 'CH1*CH2'),
            ]),
            'ref': self._build_simple_menu(tr('tool.tektronix_scope.side_ref'), [
                ('SELect:REF1 ON', _L('显示 REF1', 'Show REF1')),
                ('SELect:REF1 OFF', _L('关闭 REF1', 'Hide REF1')),
            ]),
            'bus1': self._build_simple_menu(tr('tool.tektronix_scope.side_bus1'), [
                ('SELect:BUS1 ON', _L('显示 B1', 'Show B1')),
                ('SELect:BUS1 OFF', _L('关闭 B1', 'Hide B1')),
            ]),
            'bus2': self._build_simple_menu(tr('tool.tektronix_scope.side_bus2'), [
                ('SELect:BUS2 ON', _L('显示 B2', 'Show B2')),
                ('SELect:BUS2 OFF', _L('关闭 B2', 'Hide B2')),
            ]),
            'afg': self._build_simple_menu(tr('tool.tektronix_scope.side_afg'), [
                ('AFG:OUTPut:STATE ON', _L('AFG 输出开', 'AFG Output ON')),
                ('AFG:OUTPut:STATE OFF', _L('AFG 输出关', 'AFG Output OFF')),
                ('AFG:FUNCtion SINusoid', _L('正弦', 'Sine')),
                ('AFG:FUNCtion SQUare', _L('方波', 'Square')),
            ]),
            'rf': self._build_simple_menu(tr('tool.tektronix_scope.side_rf'), [
                ('SELect:RF_NORMal ON', _L('RF Normal 开', 'RF Normal ON')),
                ('SELect:RF_NORMal OFF', _L('RF Normal 关', 'RF Normal OFF')),
            ]),
            'test': self._build_simple_menu(tr('tool.tektronix_scope.side_test'), [
                ('*TST?', _L('自检 *TST?', 'Self-test *TST?')),
                ('DIAg:LOOP:STATE?', _L('诊断循环状态', 'Diag loop state')),
            ]),
            'save_recall': self._build_simple_menu(tr('tool.tektronix_scope.side_save_recall'), [
                ('SAVe:SETUp "setup1.set"', _L('保存设置 setup1', 'Save setup1')),
                ('RECAll:SETUp "setup1.set"', _L('调出设置 setup1', 'Recall setup1')),
                ('SAVe:IMAGe "shot.png"', _L('保存图像', 'Save image')),
            ]),
            'utility': self._build_simple_menu(tr('tool.tektronix_scope.side_utility'), [
                ('*IDN?', _L('查询 *IDN?', 'Query *IDN?')),
                ('*RST', _L('复位 *RST', 'Reset *RST')),
                ('HEADER OFF', _L('关闭响应头', 'Header OFF')),
            ]),
            'intensity': self._build_intensity_menu,
        }
        builder = builders.get(key)
        if builder is None:
            self._log(f'menu not implemented: {key}')
            return
        title, widget = builder()
        self.front.show_side_menu(title, widget)

'''

path.write_text(text[:start] + new + text[end:], encoding='utf-8')
print('ok', start, end)
