# TODO this can break, as MWC is still in beta, so maybe migrate to MDC:
# https://github.com/material-components/material-components-web

import panel as pn
import param
from panel.reactive import ReactiveHTML

# pn.extension()

required_modules = pn.pane.HTML(
    """
    <script type="module" src="https://unpkg.com/@material/mwc-button?module"></script>
    <script type="module" src="https://unpkg.com/@material/mwc-slider?module"></script>
    <script type="module" src="https://unpkg.com/@material/mwc-switch?module"></script>
"""
)


class MaterialButton(ReactiveHTML):

    index = param.Integer(default=0)
    _template = (
        '<mwc-button raised label="${index}" id="dummy" onclick="${_img_click}"></mwc-button>'
    )

    def _img_click(self, event):
        self.index += 1


class _MaterialSwitchOff(ReactiveHTML):
    initial_value = param.Boolean(False)
    value = False

    _template = (
        '<mwc-switch id="dummy" selected="${initial_value}" onclick="${_switch}"></mwc-switch>'
    )

    def _switch(self, event):
        # self.event = event
        self.value = not self.value


class _MaterialSwitchOn(ReactiveHTML):
    initial_value = param.Boolean(True)
    value = True

    _template = (
        '<mwc-switch id="dummy" selected="${initial_value}" onclick="${_switch}"></mwc-switch>'
    )

    def _switch(self, event):
        # self.event = event
        self.value = not self.value


# TODO is there a way to do this cleanly?
class MaterialSwitch:
    def __new__(self, *args, **kwargs):
        if kwargs["initial_value"]:
            return _MaterialSwitchOn(*args, **kwargs)
        else:
            return _MaterialSwitchOff(*args, **kwargs)
