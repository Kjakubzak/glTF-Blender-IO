# Copyright 2018-2021 The glTF-Blender-IO authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Export-dialog panel of the KHR_character package (drawn through exporter_extension_layout_draw).


def draw_export_panel(context, layout):
    operator = context.space_data.active_operator
    if operator is None or not hasattr(operator, 'export_khr_character'):
        return
    header, body = layout.panel('GLTF_export_khr_character', default_closed=True)
    header.use_property_split = False
    header.prop(operator, 'export_khr_character', text='')
    header.label(text='KHR_character')
    if body:
        body.active = operator.export_khr_character
        body.prop(operator, 'export_khr_strict')
