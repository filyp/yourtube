import panel as pn
import param
from panel.reactive import ReactiveHTML

# I import both MDC and MWC, because in MWC button height cannot be set
# and in MDC, I wasn't able to make switches
# TODO we should migrate to MDC completely or even better, vuetify
required_modules = pn.pane.HTML(
    """
    <head>
        <link href="https://unpkg.com/material-components-web@latest/dist/material-components-web.min.css" rel="stylesheet">
        <script src="https://unpkg.com/material-components-web@latest/dist/material-components-web.min.js"></script>
    </head>
    <head>
        <link rel="stylesheet" href="https://fonts.googleapis.com/icon?family=Material+Icons">
    </head>

    <script type="module" src="https://unpkg.com/@material/mwc-switch?module"></script>
"""
)


class MaterialButton(ReactiveHTML):
    label = param.String("")
    style = param.String("")

    _template = """
        <button class="mdc-button mdc-button--raised" onclick="${on_click}" 
         id="button_id" style="${style}">
            <span class="mdc-button__ripple"></span>
            <span class="mdc-button__label">${label}</span>
        </button>
        """

    def on_click(self, event):
        pass


class _MaterialSwitch(ReactiveHTML):
    initial_value = param.Boolean(False)
    value = False

    _template = """
        <mwc-switch id="switch_id" selected="${initial_value}" onclick="${_switch}"></mwc-switch>
    """

    # TODO switching this way is dangerous, we should read the switch value directly
    def _switch(self, event):
        # self.event = event
        self.value = not self.value


# TODO is there a cleaner way to do this?
class MaterialSwitch:
    def __new__(self, *args, **kwargs):
        switch = _MaterialSwitch(*args, **kwargs)
        if kwargs["initial_value"]:
            switch.initial_value = True
            switch.value = True
        else:
            switch.initial_value = False
            switch.value = False
        return switch
