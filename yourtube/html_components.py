import panel as pn
import param
from panel.reactive import ReactiveHTML

from yourtube.file_operations import id_to_url

id_to_thumbnail = "https://i.ytimg.com/vi/{}/mqdefault.jpg"
# id_to_thumbnail = "https://i.ytimg.com/vi/{}/maxresdefault.jpg"
# hq and sd usually has black stripes
# mq < hq < sd < maxres

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


# class MaterialButton(ReactiveHTML):
#     label = param.String("")
#     style = param.String("")

#     _template = """
#         <v-btn>eeee</v-btn>
#         """

#     def on_click(self, event):
#         pass


class _MaterialSwitch(ReactiveHTML):
    initial_value = param.Boolean(False)
    value = False

    _template = """
        <mwc-switch id="switch_id" selected="${initial_value}" onclick="${_switch}"></mwc-switch>
    """
    # _template = """
    #     <button id="switch_id" class="mdc-switch mdc-switch--unselected" type="button" role="switch" aria-checked="false" onclick="${_switch}>
    #         <div class="mdc-switch__track"></div>
    #         <div class="mdc-switch__handle-track">
    #             <div class="mdc-switch__handle">
    #             <div class="mdc-switch__shadow">
    #                 <div class="mdc-elevation-overlay"></div>
    #             </div>
    #             <div class="mdc-switch__ripple"></div>
    #             <div class="mdc-switch__icons">
    #                 <svg class="mdc-switch__icon mdc-switch__icon--on" viewBox="0 0 24 24">
    #                 <path d="M19.69,5.23L8.96,15.96l-4.23-4.23L2.96,13.5l6,6L21.46,7L19.69,5.23z" />
    #                 </svg>
    #                 <svg class="mdc-switch__icon mdc-switch__icon--off" viewBox="0 0 24 24">
    #                 <path d="M20 13H4v-2h16v2z" />
    #                 </svg>
    #             </div>
    #             </div>
    #         </div>
    #     </button>
    # """

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


class MaterialTextField(ReactiveHTML):
    # source: https://panel.holoviz.org/gallery/components/MaterialUI.html

    value = param.String(default="")
    label = param.String(default="")

    _template = """
    <label id="text-field" class="mdc-text-field mdc-text-field--filled">
      <span class="mdc-text-field__ripple"></span>
      <span class="mdc-floating-label">${label}</span>
      <input id="text-input" type="text" class="mdc-text-field__input" aria-labelledby="my-label" value="${value}"></input>
      <span class="mdc-line-ripple"></span>
    </label>
    """

    _dom_events = {"text-input": ["change"]}

    _scripts = {"render": "mdc.textField.MDCTextField.attachTo(text_field);"}


class MaterialSlider(ReactiveHTML):
    # source: https://panel.holoviz.org/gallery/components/MaterialUI.html

    end = param.Number(default=100)

    start = param.Number(default=0)

    value = param.Number(default=50)

    _template = """
    <div id="mdc-slider" class="mdc-slider" style="width: ${model.width}px">
      <input id="slider-input" class="mdc-slider__input" min="${start}" max="${end}" value="${value}">
      </input>
      <div class="mdc-slider__track">
        <div class="mdc-slider__track--inactive"></div>
        <div class="mdc-slider__track--active">
          <div class="mdc-slider__track--active_fill"></div>
        </div>
      </div>
      <div class="mdc-slider__thumb">
        <div class="mdc-slider__thumb-knob"></div>
      </div>
    </div>
    """

    _scripts = {
        "render": """
            slider_input.setAttribute('value', data.value)
        """,
        # state.slider = mdc.slider.MDCSlider.attachTo(mdc_slider)
        "value": """
            state.slider.setValue(data.value)
        """,
    }


class VideoGrid(ReactiveHTML):
    ids = param.List(item_type=str)
    texts = param.List(item_type=str)
    _dummy = param.Boolean(False)

    def update(self):
        # this is needed because just updating the lists, doesn't update the grid
        self._dummy = not self._dummy

    def __init__(self, n, num_of_columns, column_width, row_height, grid_gap):
        super().__init__()

        css_style = """
            <style>
            .wrapper {{
              display: grid;
              grid-template-columns:{};
              grid-gap: {}px;
            }}
            </style>
        """.format(
            f"{column_width}px " * num_of_columns,
            grid_gap,
        )

        html = '<div class="wrapper">'
        for i in range(n):
            id_handle = "${ids[" + str(i) + "]}"
            text_handle = "${texts[" + str(i) + "]}"
            video_url = id_to_url.format(id_handle)
            image_url = id_to_thumbnail.format(id_handle)

            html += f"""
            <div style="height: {row_height}px;">
                <a href="{video_url}" target="_blank"><img src="{image_url}" style='width: 100%; object-fit: contain'/></a>
                <a href="{video_url}" target="_blank" style="text-decoration: none; color:#EEEEEE;">{text_handle}</a>
            </div>"""
        html += "</div>"

        self._template = css_style + html + "${_dummy}"
