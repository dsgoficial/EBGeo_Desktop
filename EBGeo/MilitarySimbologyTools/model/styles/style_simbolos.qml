<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis styleCategories="Symbology|Labeling|Fields|Forms" version="3.40.8-Bratislava" labelsEnabled="0">
  <renderer-v2 referencescale="-1" forceraster="0" symbollevels="0" type="RuleRenderer" enableorderby="0">
    <rules key="{f4514559-1afe-4fb2-b38e-1ce9e9964057}">
      <rule symbol="0" key="{d6a80969-162a-4472-b3a0-d9ade21d4f10}" filter="&quot;caminho_imagem&quot; is not NULL"/>
      <rule symbol="1" key="{c7064b76-ba69-4a0d-bea1-756dda5e5c46}" filter="ELSE"/>
    </rules>
    <symbols>
      <symbol name="0" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="marker" frame_rate="10">
        <data_defined_properties>
          <Option type="Map">
            <Option name="name" value="" type="QString"/>
            <Option name="properties"/>
            <Option name="type" value="collection" type="QString"/>
          </Option>
        </data_defined_properties>
        <layer id="{741ad76a-0f6f-4a17-bfd4-c9f2c5dc4bf6}" locked="0" pass="0" enabled="1" class="RasterMarker">
          <Option type="Map">
            <Option name="alpha" value="1" type="QString"/>
            <Option name="angle" value="0" type="QString"/>
            <Option name="fixedAspectRatio" value="0" type="QString"/>
            <Option name="horizontal_anchor_point" value="1" type="QString"/>
            <Option name="imageFile" value="" type="QString"/>
            <Option name="offset" value="0,0" type="QString"/>
            <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
            <Option name="offset_unit" value="MM" type="QString"/>
            <Option name="scale_method" value="diameter" type="QString"/>
            <Option name="size" value="2" type="QString"/>
            <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
            <Option name="size_unit" value="RenderMetersInMapUnits" type="QString"/>
            <Option name="vertical_anchor_point" value="1" type="QString"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties" type="Map">
                <Option name="angle" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="coalesce(&quot;simb_rotacao&quot;, 0)" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="name" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="field" value="caminho_imagem" type="QString"/>
                  <Option name="type" value="2" type="int"/>
                </Option>
                <Option name="width" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="if(&quot;tipo_tamanho&quot;=2,  coalesce(&quot;simb_tamanho&quot;, 1000), coalesce(&quot;simb_tamanho&quot;/100000, 0.01)*@map_scale )" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
              </Option>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </data_defined_properties>
        </layer>
      </symbol>
      <symbol name="1" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="marker" frame_rate="10">
        <data_defined_properties>
          <Option type="Map">
            <Option name="name" value="" type="QString"/>
            <Option name="properties"/>
            <Option name="type" value="collection" type="QString"/>
          </Option>
        </data_defined_properties>
        <layer id="{31a9a6fc-f445-4d6b-b794-cdf25c25044b}" locked="0" pass="0" enabled="1" class="SvgMarker">
          <Option type="Map">
            <Option name="angle" value="0" type="QString"/>
            <Option name="color" value="0,0,0,255,rgb:0,0,0,1" type="QString"/>
            <Option name="fixedAspectRatio" value="0" type="QString"/>
            <Option name="horizontal_anchor_point" value="1" type="QString"/>
            <Option name="name" value="gpsicons/question.svg" type="QString"/>
            <Option name="offset" value="0,0" type="QString"/>
            <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
            <Option name="offset_unit" value="MM" type="QString"/>
            <Option name="outline_color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
            <Option name="outline_width" value="0" type="QString"/>
            <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
            <Option name="outline_width_unit" value="MM" type="QString"/>
            <Option name="parameters"/>
            <Option name="scale_method" value="diameter" type="QString"/>
            <Option name="size" value="20" type="QString"/>
            <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
            <Option name="size_unit" value="MM" type="QString"/>
            <Option name="vertical_anchor_point" value="1" type="QString"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties" type="Map">
                <Option name="width" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="if(&quot;tipo_tamanho&quot;=2,  coalesce(&quot;simb_tamanho&quot;, 1000), coalesce(&quot;simb_tamanho&quot;/10000, 0.1)*@map_scale )" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
              </Option>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </data_defined_properties>
        </layer>
      </symbol>
    </symbols>
    <data-defined-properties>
      <Option type="Map">
        <Option name="name" value="" type="QString"/>
        <Option name="properties"/>
        <Option name="type" value="collection" type="QString"/>
      </Option>
    </data-defined-properties>
  </renderer-v2>
  <selection mode="Default">
    <selectionColor invalid="1"/>
    <selectionSymbol>
      <symbol name="" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="marker" frame_rate="10">
        <data_defined_properties>
          <Option type="Map">
            <Option name="name" value="" type="QString"/>
            <Option name="properties"/>
            <Option name="type" value="collection" type="QString"/>
          </Option>
        </data_defined_properties>
        <layer id="{a3e403fc-5090-4310-846c-10682804ae58}" locked="0" pass="0" enabled="1" class="SimpleMarker">
          <Option type="Map">
            <Option name="angle" value="0" type="QString"/>
            <Option name="cap_style" value="square" type="QString"/>
            <Option name="color" value="255,0,0,255,rgb:1,0,0,1" type="QString"/>
            <Option name="horizontal_anchor_point" value="1" type="QString"/>
            <Option name="joinstyle" value="bevel" type="QString"/>
            <Option name="name" value="circle" type="QString"/>
            <Option name="offset" value="0,0" type="QString"/>
            <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
            <Option name="offset_unit" value="MM" type="QString"/>
            <Option name="outline_color" value="35,35,35,255,rgb:0.13725490196078433,0.13725490196078433,0.13725490196078433,1" type="QString"/>
            <Option name="outline_style" value="solid" type="QString"/>
            <Option name="outline_width" value="0" type="QString"/>
            <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
            <Option name="outline_width_unit" value="MM" type="QString"/>
            <Option name="scale_method" value="diameter" type="QString"/>
            <Option name="size" value="2" type="QString"/>
            <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
            <Option name="size_unit" value="MM" type="QString"/>
            <Option name="vertical_anchor_point" value="1" type="QString"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties"/>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </data_defined_properties>
        </layer>
      </symbol>
    </selectionSymbol>
  </selection>
  <blendMode>0</blendMode>
  <featureBlendMode>0</featureBlendMode>
  <fieldConfiguration>
    <field name="fid" configurationFlags="NoFlag">
      <editWidget type="TextEdit">
        <config>
          <Option/>
        </config>
      </editWidget>
    </field>
    <field name="nome" configurationFlags="NoFlag">
      <editWidget type="TextEdit">
        <config>
          <Option/>
        </config>
      </editWidget>
    </field>
    <field name="simb_rotacao" configurationFlags="NoFlag">
      <editWidget type="TextEdit">
        <config>
          <Option/>
        </config>
      </editWidget>
    </field>
    <field name="simb_tamanho" configurationFlags="NoFlag">
      <editWidget type="TextEdit">
        <config>
          <Option/>
        </config>
      </editWidget>
    </field>
    <field name="caminho_imagem" configurationFlags="NoFlag">
      <editWidget type="ExternalResource">
        <config>
          <Option type="Map">
            <Option name="DocumentViewer" value="0" type="int"/>
            <Option name="DocumentViewerHeight" value="0" type="int"/>
            <Option name="DocumentViewerWidth" value="0" type="int"/>
            <Option name="FileWidget" value="true" type="bool"/>
            <Option name="FileWidgetButton" value="true" type="bool"/>
            <Option name="FileWidgetFilter" value="*.png *.PNG" type="QString"/>
            <Option name="PropertyCollection" type="Map">
              <Option name="name" type="invalid"/>
              <Option name="properties" type="invalid"/>
              <Option name="type" value="collection" type="QString"/>
            </Option>
            <Option name="RelativeStorage" value="0" type="int"/>
            <Option name="StorageAuthConfigId" type="invalid"/>
            <Option name="StorageMode" value="0" type="int"/>
            <Option name="StorageType" type="invalid"/>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="tipo_tamanho" configurationFlags="NoFlag">
      <editWidget type="ValueMap">
        <config>
          <Option type="Map">
            <Option name="map" type="List">
              <Option type="Map">
                <Option name="Milímetros na tela" value="1" type="QString"/>
              </Option>
              <Option type="Map">
                <Option name="Metros no terreno" value="2" type="QString"/>
              </Option>
            </Option>
          </Option>
        </config>
      </editWidget>
    </field>
  </fieldConfiguration>
  <aliases>
    <alias name="" field="fid" index="0"/>
    <alias name="" field="nome" index="1"/>
    <alias name="" field="simb_rotacao" index="2"/>
    <alias name="" field="simb_tamanho" index="3"/>
    <alias name="" field="caminho_imagem" index="4"/>
    <alias name="" field="tipo_tamanho" index="5"/>
  </aliases>
  <splitPolicies>
    <policy policy="Duplicate" field="fid"/>
    <policy policy="Duplicate" field="nome"/>
    <policy policy="Duplicate" field="simb_rotacao"/>
    <policy policy="Duplicate" field="simb_tamanho"/>
    <policy policy="DefaultValue" field="caminho_imagem"/>
    <policy policy="DefaultValue" field="tipo_tamanho"/>
  </splitPolicies>
  <duplicatePolicies>
    <policy policy="Duplicate" field="fid"/>
    <policy policy="Duplicate" field="nome"/>
    <policy policy="Duplicate" field="simb_rotacao"/>
    <policy policy="Duplicate" field="simb_tamanho"/>
    <policy policy="Duplicate" field="caminho_imagem"/>
    <policy policy="Duplicate" field="tipo_tamanho"/>
  </duplicatePolicies>
  <defaults>
    <default expression="" applyOnUpdate="0" field="fid"/>
    <default expression="" applyOnUpdate="0" field="nome"/>
    <default expression="" applyOnUpdate="0" field="simb_rotacao"/>
    <default expression="" applyOnUpdate="0" field="simb_tamanho"/>
    <default expression="" applyOnUpdate="0" field="caminho_imagem"/>
    <default expression="1" applyOnUpdate="0" field="tipo_tamanho"/>
  </defaults>
  <constraints>
    <constraint exp_strength="0" constraints="3" unique_strength="1" notnull_strength="1" field="fid"/>
    <constraint exp_strength="0" constraints="0" unique_strength="0" notnull_strength="0" field="nome"/>
    <constraint exp_strength="0" constraints="0" unique_strength="0" notnull_strength="0" field="simb_rotacao"/>
    <constraint exp_strength="0" constraints="0" unique_strength="0" notnull_strength="0" field="simb_tamanho"/>
    <constraint exp_strength="0" constraints="1" unique_strength="0" notnull_strength="1" field="caminho_imagem"/>
    <constraint exp_strength="0" constraints="1" unique_strength="0" notnull_strength="2" field="tipo_tamanho"/>
  </constraints>
  <constraintExpressions>
    <constraint desc="" exp="" field="fid"/>
    <constraint desc="" exp="" field="nome"/>
    <constraint desc="" exp="" field="simb_rotacao"/>
    <constraint desc="" exp="" field="simb_tamanho"/>
    <constraint desc="" exp="" field="caminho_imagem"/>
    <constraint desc="" exp="" field="tipo_tamanho"/>
  </constraintExpressions>
  <expressionfields/>
  <editform tolerant="1"></editform>
  <editforminit/>
  <editforminitcodesource>0</editforminitcodesource>
  <editforminitfilepath></editforminitfilepath>
  <editforminitcode><![CDATA[# -*- coding: utf-8 -*-
"""
QGIS forms can have a Python function that is called when the form is
opened.

Use this function to add extra logic to your forms.

Enter the name of the function in the "Python Init function"
field.
An example follows:
"""
from qgis.PyQt.QtWidgets import QWidget

def my_form_open(dialog, layer, feature):
    geom = feature.geometry()
    control = dialog.findChild(QWidget, "MyLineEdit")
]]></editforminitcode>
  <featformsuppress>0</featformsuppress>
  <editorlayout>generatedlayout</editorlayout>
  <editable>
    <field name="caminho_imagem" editable="1"/>
    <field name="fid" editable="1"/>
    <field name="nome" editable="1"/>
    <field name="path" editable="1"/>
    <field name="simb_rot" editable="1"/>
    <field name="simb_rotacao" editable="1"/>
    <field name="simb_size" editable="1"/>
    <field name="simb_tamanho" editable="1"/>
    <field name="tipo_tamanho" editable="1"/>
  </editable>
  <labelOnTop>
    <field name="caminho_imagem" labelOnTop="0"/>
    <field name="fid" labelOnTop="0"/>
    <field name="nome" labelOnTop="0"/>
    <field name="path" labelOnTop="0"/>
    <field name="simb_rot" labelOnTop="0"/>
    <field name="simb_rotacao" labelOnTop="0"/>
    <field name="simb_size" labelOnTop="0"/>
    <field name="simb_tamanho" labelOnTop="0"/>
    <field name="tipo_tamanho" labelOnTop="0"/>
  </labelOnTop>
  <reuseLastValue>
    <field name="caminho_imagem" reuseLastValue="0"/>
    <field name="fid" reuseLastValue="0"/>
    <field name="nome" reuseLastValue="0"/>
    <field name="path" reuseLastValue="0"/>
    <field name="simb_rot" reuseLastValue="0"/>
    <field name="simb_rotacao" reuseLastValue="0"/>
    <field name="simb_size" reuseLastValue="0"/>
    <field name="simb_tamanho" reuseLastValue="0"/>
    <field name="tipo_tamanho" reuseLastValue="0"/>
  </reuseLastValue>
  <dataDefinedFieldProperties/>
  <widgets/>
  <layerGeometryType>0</layerGeometryType>
</qgis>
