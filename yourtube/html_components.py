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
