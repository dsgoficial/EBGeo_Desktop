<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis styleCategories="Symbology|Labeling|Fields|Forms" version="3.40.8-Bratislava" labelsEnabled="1">
  <renderer-v2 referencescale="-1" forceraster="0" symbollevels="0" type="RuleRenderer" enableorderby="0">
    <rules key="{70e0b518-c9da-4210-ac45-ea6d96371d51}">
      <rule label="Linha" key="{0a725b29-73d2-4092-a630-109d8234ade4}">
        <rule symbol="0" label="topas iguais" key="{ddd28d47-f01e-4c75-bf7c-8e386628eed8}" filter=" &quot;tropa_esq&quot; =  &quot;tropa_dir&quot;"/>
        <rule symbol="1" label="topas diferentes" key="{d7b64ee4-a386-442d-95b1-161e5fb1f576}" filter=" &quot;tropa_esq&quot; !=  &quot;tropa_dir&quot;"/>
      </rule>
      <rule label="Simbolo" key="{34ffbd4e-13d0-4d22-8d17-5eb2dc82fd6f}">
        <rule label="tropas iguais" key="{2e941705-6f06-40f2-81f7-7efcc2bb2663}" filter=" &quot;tropa_esq&quot; = &quot;tropa_dir&quot;">
          <rule symbol="2" label="pelotao" key="{a56880b4-9b35-4ce0-bae0-11382cf7b1bc}" filter=" &quot;tropa_esq&quot;  = 6"/>
          <rule symbol="3" label="demais" key="{4cfca3c8-98f9-4e99-a682-fb9f67ba72af}" filter="&quot;tropa_dir&quot; != 6"/>
        </rule>
        <rule label="tropas diferentes" key="{5b463d1b-4614-4c60-8667-0e75a333b774}" filter="&quot;tropa_esq&quot; != &quot;tropa_dir&quot;">
          <rule symbol="4" label="pelotao" key="{ff828a31-fc02-4ded-a5f3-589329ca0055}" filter="&quot;tropa_esq&quot;  = 6 or  &quot;tropa_dir&quot;  = 6"/>
          <rule symbol="5" label="demais" key="{6e11a895-d521-4e1f-994e-5ace39c52303}" filter="&quot;tropa_dir&quot; != 6 or &quot;tropa_esq&quot; != 6"/>
        </rule>
      </rule>
    </rules>
    <symbols>
      <symbol name="0" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="line" frame_rate="10">
        <data_defined_properties>
          <Option type="Map">
            <Option name="name" value="" type="QString"/>
            <Option name="properties"/>
            <Option name="type" value="collection" type="QString"/>
          </Option>
        </data_defined_properties>
        <layer id="{c4278af2-fe1b-4b69-bf01-44b91eeb260b}" locked="0" pass="0" enabled="1" class="GeometryGenerator">
          <Option type="Map">
            <Option name="SymbolType" value="Line" type="QString"/>
            <Option name="geometryModifier" value="difference( $geometry,buffer(line_interpolate_point($geometry, length ($geometry)/2), &#xd;&#xa;CASE&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; in (3,5) THEN 110&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; in (2,4,7) THEN 200&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; in (1,6) THEN 300&#xd;&#xa;END&#xd;&#xa;)&#xd;&#xa;)&#xd;&#xa;&#xd;&#xa;&#xd;&#xa;&#xd;&#xa;" type="QString"/>
            <Option name="units" value="MapUnit" type="QString"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties"/>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </data_defined_properties>
          <symbol name="@0@0" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="line" frame_rate="10">
            <data_defined_properties>
              <Option type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties"/>
                <Option name="type" value="collection" type="QString"/>
              </Option>
            </data_defined_properties>
            <layer id="{7114477b-b855-4515-95f8-ebdb1027d630}" locked="0" pass="0" enabled="1" class="SimpleLine">
              <Option type="Map">
                <Option name="align_dash_pattern" value="0" type="QString"/>
                <Option name="capstyle" value="square" type="QString"/>
                <Option name="customdash" value="5;2" type="QString"/>
                <Option name="customdash_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="customdash_unit" value="MM" type="QString"/>
                <Option name="dash_pattern_offset" value="0" type="QString"/>
                <Option name="dash_pattern_offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="dash_pattern_offset_unit" value="MM" type="QString"/>
                <Option name="draw_inside_polygon" value="0" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="line_color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                <Option name="line_style" value="solid" type="QString"/>
                <Option name="line_width" value="20" type="QString"/>
                <Option name="line_width_unit" value="MapUnit" type="QString"/>
                <Option name="offset" value="0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="ring_filter" value="0" type="QString"/>
                <Option name="trim_distance_end" value="0" type="QString"/>
                <Option name="trim_distance_end_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="trim_distance_end_unit" value="MM" type="QString"/>
                <Option name="trim_distance_start" value="0" type="QString"/>
                <Option name="trim_distance_start_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="trim_distance_start_unit" value="MM" type="QString"/>
                <Option name="tweak_dash_pattern_on_corners" value="0" type="QString"/>
                <Option name="use_custom_dash" value="0" type="QString"/>
                <Option name="width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties" type="Map">
                    <Option name="outlineWidth" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="&quot;Borda&quot;" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                  </Option>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
            <layer id="{5c0efdad-3002-4fc4-b07e-b151891fe8a0}" locked="0" pass="0" enabled="1" class="SimpleLine">
              <Option type="Map">
                <Option name="align_dash_pattern" value="0" type="QString"/>
                <Option name="capstyle" value="square" type="QString"/>
                <Option name="customdash" value="5;2" type="QString"/>
                <Option name="customdash_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="customdash_unit" value="MM" type="QString"/>
                <Option name="dash_pattern_offset" value="0" type="QString"/>
                <Option name="dash_pattern_offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="dash_pattern_offset_unit" value="MM" type="QString"/>
                <Option name="draw_inside_polygon" value="0" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="line_color" value="0,0,0,255,rgb:0,0,0,1" type="QString"/>
                <Option name="line_style" value="solid" type="QString"/>
                <Option name="line_width" value="20" type="QString"/>
                <Option name="line_width_unit" value="MapUnit" type="QString"/>
                <Option name="offset" value="0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="ring_filter" value="0" type="QString"/>
                <Option name="trim_distance_end" value="0" type="QString"/>
                <Option name="trim_distance_end_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="trim_distance_end_unit" value="MM" type="QString"/>
                <Option name="trim_distance_start" value="0" type="QString"/>
                <Option name="trim_distance_start_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="trim_distance_start_unit" value="MM" type="QString"/>
                <Option name="tweak_dash_pattern_on_corners" value="0" type="QString"/>
                <Option name="use_custom_dash" value="0" type="QString"/>
                <Option name="width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
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
        </layer>
      </symbol>
      <symbol name="1" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="line" frame_rate="10">
        <data_defined_properties>
          <Option type="Map">
            <Option name="name" value="" type="QString"/>
            <Option name="properties"/>
            <Option name="type" value="collection" type="QString"/>
          </Option>
        </data_defined_properties>
        <layer id="{8dae990a-1845-4223-90f9-54224787c2f1}" locked="0" pass="0" enabled="1" class="GeometryGenerator">
          <Option type="Map">
            <Option name="SymbolType" value="Line" type="QString"/>
            <Option name="geometryModifier" value="difference(difference( $geometry,buffer(line_interpolate_point($geometry, length ($geometry)/2+500), &#xd;&#xa;CASE&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; in (3,5) THEN 110&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; in (2,4,7) THEN 200&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; in (1,6) THEN 300&#xd;&#xa;END&#xd;&#xa;)&#xd;&#xa;),&#xd;&#xa;buffer(line_interpolate_point($geometry, length ($geometry)/2-500), &#xd;&#xa;CASE&#xd;&#xa;&#x9;WHEN &quot;tropa_esq&quot; in (3,5) THEN 110&#xd;&#xa;&#x9;WHEN &quot;tropa_esq&quot; in (2,4,7) THEN 200&#xd;&#xa;&#x9;WHEN &quot;tropa_esq&quot; in (1,6) THEN 300&#xd;&#xa;END&#xd;&#xa;)&#xd;&#xa;)&#xd;&#xa; &#xd;&#xa;&#xd;&#xa;&#xd;&#xa;" type="QString"/>
            <Option name="units" value="MapUnit" type="QString"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties"/>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </data_defined_properties>
          <symbol name="@1@0" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="line" frame_rate="10">
            <data_defined_properties>
              <Option type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties"/>
                <Option name="type" value="collection" type="QString"/>
              </Option>
            </data_defined_properties>
            <layer id="{26946eec-931d-4bab-b4e0-d1421a6bbc27}" locked="0" pass="0" enabled="1" class="SimpleLine">
              <Option type="Map">
                <Option name="align_dash_pattern" value="0" type="QString"/>
                <Option name="capstyle" value="square" type="QString"/>
                <Option name="customdash" value="5;2" type="QString"/>
                <Option name="customdash_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="customdash_unit" value="MM" type="QString"/>
                <Option name="dash_pattern_offset" value="0" type="QString"/>
                <Option name="dash_pattern_offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="dash_pattern_offset_unit" value="MM" type="QString"/>
                <Option name="draw_inside_polygon" value="0" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="line_color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                <Option name="line_style" value="solid" type="QString"/>
                <Option name="line_width" value="20" type="QString"/>
                <Option name="line_width_unit" value="MapUnit" type="QString"/>
                <Option name="offset" value="0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="ring_filter" value="0" type="QString"/>
                <Option name="trim_distance_end" value="0" type="QString"/>
                <Option name="trim_distance_end_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="trim_distance_end_unit" value="MM" type="QString"/>
                <Option name="trim_distance_start" value="0" type="QString"/>
                <Option name="trim_distance_start_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="trim_distance_start_unit" value="MM" type="QString"/>
                <Option name="tweak_dash_pattern_on_corners" value="0" type="QString"/>
                <Option name="use_custom_dash" value="0" type="QString"/>
                <Option name="width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties" type="Map">
                    <Option name="outlineWidth" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="&quot;Borda&quot;" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                  </Option>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
            <layer id="{084e5788-1727-41d7-b854-ae86c09eabc3}" locked="0" pass="0" enabled="1" class="SimpleLine">
              <Option type="Map">
                <Option name="align_dash_pattern" value="0" type="QString"/>
                <Option name="capstyle" value="square" type="QString"/>
                <Option name="customdash" value="5;2" type="QString"/>
                <Option name="customdash_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="customdash_unit" value="MM" type="QString"/>
                <Option name="dash_pattern_offset" value="0" type="QString"/>
                <Option name="dash_pattern_offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="dash_pattern_offset_unit" value="MM" type="QString"/>
                <Option name="draw_inside_polygon" value="0" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="line_color" value="0,0,0,255,rgb:0,0,0,1" type="QString"/>
                <Option name="line_style" value="solid" type="QString"/>
                <Option name="line_width" value="20" type="QString"/>
                <Option name="line_width_unit" value="MapUnit" type="QString"/>
                <Option name="offset" value="0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="ring_filter" value="0" type="QString"/>
                <Option name="trim_distance_end" value="0" type="QString"/>
                <Option name="trim_distance_end_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="trim_distance_end_unit" value="MM" type="QString"/>
                <Option name="trim_distance_start" value="0" type="QString"/>
                <Option name="trim_distance_start_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="trim_distance_start_unit" value="MM" type="QString"/>
                <Option name="tweak_dash_pattern_on_corners" value="0" type="QString"/>
                <Option name="use_custom_dash" value="0" type="QString"/>
                <Option name="width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
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
        </layer>
      </symbol>
      <symbol name="2" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="line" frame_rate="10">
        <data_defined_properties>
          <Option type="Map">
            <Option name="name" value="" type="QString"/>
            <Option name="properties"/>
            <Option name="type" value="collection" type="QString"/>
          </Option>
        </data_defined_properties>
        <layer id="{dcffd4d2-1a32-40ea-85de-c50ba5dd36fc}" locked="0" pass="0" enabled="1" class="GeometryGenerator">
          <Option type="Map">
            <Option name="SymbolType" value="Marker" type="QString"/>
            <Option name="geometryModifier" value="line_interpolate_point($geometry, length ($geometry)/2+175.0027) " type="QString"/>
            <Option name="units" value="MapUnit" type="QString"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties"/>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </data_defined_properties>
          <symbol name="@2@0" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="marker" frame_rate="10">
            <data_defined_properties>
              <Option type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties"/>
                <Option name="type" value="collection" type="QString"/>
              </Option>
            </data_defined_properties>
            <layer id="{25263bdb-bd75-42f4-abe6-4e7eb0aadd14}" locked="0" pass="0" enabled="1" class="SimpleMarker">
              <Option type="Map">
                <Option name="angle" value="0" type="QString"/>
                <Option name="cap_style" value="square" type="QString"/>
                <Option name="color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                <Option name="horizontal_anchor_point" value="1" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="name" value="circle" type="QString"/>
                <Option name="offset" value="0,0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="outline_color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                <Option name="outline_style" value="solid" type="QString"/>
                <Option name="outline_width" value="5" type="QString"/>
                <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                <Option name="scale_method" value="diameter" type="QString"/>
                <Option name="size" value="150" type="QString"/>
                <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="size_unit" value="MapUnit" type="QString"/>
                <Option name="vertical_anchor_point" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties" type="Map">
                    <Option name="angle" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value=" &quot;Rot_DIR&quot; " type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="outlineWidth" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="&quot;Borda&quot; *0.3" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="size" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="120  +  &quot;Borda&quot;" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                  </Option>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
            <layer id="{62ec4253-6a18-4295-996d-5e28ffe9cfba}" locked="0" pass="0" enabled="1" class="SimpleMarker">
              <Option type="Map">
                <Option name="angle" value="0" type="QString"/>
                <Option name="cap_style" value="square" type="QString"/>
                <Option name="color" value="0,0,0,255,rgb:0,0,0,1" type="QString"/>
                <Option name="horizontal_anchor_point" value="1" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="name" value="circle" type="QString"/>
                <Option name="offset" value="0,0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="outline_color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                <Option name="outline_style" value="solid" type="QString"/>
                <Option name="outline_width" value="5" type="QString"/>
                <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                <Option name="scale_method" value="diameter" type="QString"/>
                <Option name="size" value="150" type="QString"/>
                <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="size_unit" value="MapUnit" type="QString"/>
                <Option name="vertical_anchor_point" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties" type="Map">
                    <Option name="angle" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value=" &quot;Rot_DIR&quot; " type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="outlineWidth" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="&quot;Borda&quot; *0.3" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                  </Option>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
          </symbol>
        </layer>
        <layer id="{462ad55f-0dcf-493e-a20d-d64a9bbcba8a}" locked="0" pass="0" enabled="1" class="GeometryGenerator">
          <Option type="Map">
            <Option name="SymbolType" value="Marker" type="QString"/>
            <Option name="geometryModifier" value="line_interpolate_point($geometry, length ($geometry)/2-175) " type="QString"/>
            <Option name="units" value="MapUnit" type="QString"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties"/>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </data_defined_properties>
          <symbol name="@2@1" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="marker" frame_rate="10">
            <data_defined_properties>
              <Option type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties"/>
                <Option name="type" value="collection" type="QString"/>
              </Option>
            </data_defined_properties>
            <layer id="{e22bc1ef-44a3-4c30-8260-284a38201201}" locked="0" pass="0" enabled="1" class="SimpleMarker">
              <Option type="Map">
                <Option name="angle" value="0" type="QString"/>
                <Option name="cap_style" value="square" type="QString"/>
                <Option name="color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                <Option name="horizontal_anchor_point" value="1" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="name" value="circle" type="QString"/>
                <Option name="offset" value="0,0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="outline_color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                <Option name="outline_style" value="solid" type="QString"/>
                <Option name="outline_width" value="5" type="QString"/>
                <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                <Option name="scale_method" value="diameter" type="QString"/>
                <Option name="size" value="150" type="QString"/>
                <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="size_unit" value="MapUnit" type="QString"/>
                <Option name="vertical_anchor_point" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties" type="Map">
                    <Option name="angle" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value=" &quot;Rot_DIR&quot; " type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="outlineWidth" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="&quot;Borda&quot;*0.3" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="size" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="120  +  &quot;Borda&quot;" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                  </Option>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
            <layer id="{aecae4ba-e763-40b8-b621-b450d7830261}" locked="0" pass="0" enabled="1" class="SimpleMarker">
              <Option type="Map">
                <Option name="angle" value="0" type="QString"/>
                <Option name="cap_style" value="square" type="QString"/>
                <Option name="color" value="0,0,0,255,rgb:0,0,0,1" type="QString"/>
                <Option name="horizontal_anchor_point" value="1" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="name" value="circle" type="QString"/>
                <Option name="offset" value="0,0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="outline_color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                <Option name="outline_style" value="solid" type="QString"/>
                <Option name="outline_width" value="5" type="QString"/>
                <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                <Option name="scale_method" value="diameter" type="QString"/>
                <Option name="size" value="150" type="QString"/>
                <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="size_unit" value="MapUnit" type="QString"/>
                <Option name="vertical_anchor_point" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties" type="Map">
                    <Option name="angle" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value=" &quot;Rot_DIR&quot; " type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="outlineWidth" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="&quot;Borda&quot;*0.3" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                  </Option>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
          </symbol>
        </layer>
        <layer id="{01afeaf8-975c-4b4a-a870-acde0d24ff51}" locked="0" pass="0" enabled="1" class="GeometryGenerator">
          <Option type="Map">
            <Option name="SymbolType" value="Marker" type="QString"/>
            <Option name="geometryModifier" value="line_interpolate_point($geometry, length ($geometry)/2-0.00027) " type="QString"/>
            <Option name="units" value="MapUnit" type="QString"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties"/>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </data_defined_properties>
          <symbol name="@2@2" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="marker" frame_rate="10">
            <data_defined_properties>
              <Option type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties"/>
                <Option name="type" value="collection" type="QString"/>
              </Option>
            </data_defined_properties>
            <layer id="{a76b52f6-bdfe-4d1a-aeaa-296147e75585}" locked="0" pass="0" enabled="1" class="SimpleMarker">
              <Option type="Map">
                <Option name="angle" value="0" type="QString"/>
                <Option name="cap_style" value="square" type="QString"/>
                <Option name="color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                <Option name="horizontal_anchor_point" value="1" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="name" value="circle" type="QString"/>
                <Option name="offset" value="0,0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="outline_color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                <Option name="outline_style" value="solid" type="QString"/>
                <Option name="outline_width" value="5" type="QString"/>
                <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                <Option name="scale_method" value="diameter" type="QString"/>
                <Option name="size" value="150" type="QString"/>
                <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="size_unit" value="MapUnit" type="QString"/>
                <Option name="vertical_anchor_point" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties" type="Map">
                    <Option name="angle" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value=" &quot;Rot_DIR&quot; " type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="outlineWidth" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="&quot;Borda&quot; *0.3" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="size" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="120  +  &quot;Borda&quot;" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                  </Option>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
            <layer id="{fe18994f-d6a7-475d-b7f8-8561ccac5ba2}" locked="0" pass="0" enabled="1" class="SimpleMarker">
              <Option type="Map">
                <Option name="angle" value="0" type="QString"/>
                <Option name="cap_style" value="square" type="QString"/>
                <Option name="color" value="0,0,0,255,rgb:0,0,0,1" type="QString"/>
                <Option name="horizontal_anchor_point" value="1" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="name" value="circle" type="QString"/>
                <Option name="offset" value="0,0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="outline_color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                <Option name="outline_style" value="solid" type="QString"/>
                <Option name="outline_width" value="5" type="QString"/>
                <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                <Option name="scale_method" value="diameter" type="QString"/>
                <Option name="size" value="150" type="QString"/>
                <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="size_unit" value="MapUnit" type="QString"/>
                <Option name="vertical_anchor_point" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties" type="Map">
                    <Option name="angle" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value=" &quot;Rot_DIR&quot; " type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="outlineWidth" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="&quot;Borda&quot; *0.3" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                  </Option>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
          </symbol>
        </layer>
      </symbol>
      <symbol name="3" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="line" frame_rate="10">
        <data_defined_properties>
          <Option type="Map">
            <Option name="name" value="" type="QString"/>
            <Option name="properties"/>
            <Option name="type" value="collection" type="QString"/>
          </Option>
        </data_defined_properties>
        <layer id="{04581153-7df9-4515-8116-ddd8da7e61fe}" locked="0" pass="0" enabled="1" class="GeometryGenerator">
          <Option type="Map">
            <Option name="SymbolType" value="Line" type="QString"/>
            <Option name="geometryModifier" value="make_line(&#xd;&#xa;line_interpolate_point($geometry, length ($geometry)/2+200),&#xd;&#xa;line_interpolate_point($geometry, length ($geometry)/2-200)&#xd;&#xa;) " type="QString"/>
            <Option name="units" value="MapUnit" type="QString"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties"/>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </data_defined_properties>
          <symbol name="@3@0" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="line" frame_rate="10">
            <data_defined_properties>
              <Option type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties"/>
                <Option name="type" value="collection" type="QString"/>
              </Option>
            </data_defined_properties>
            <layer id="{b434d921-76e6-4351-a99b-a329b30c7e0a}" locked="0" pass="0" enabled="1" class="MarkerLine">
              <Option type="Map">
                <Option name="average_angle_length" value="0" type="QString"/>
                <Option name="average_angle_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="average_angle_unit" value="MapUnit" type="QString"/>
                <Option name="interval" value="3" type="QString"/>
                <Option name="interval_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="interval_unit" value="MM" type="QString"/>
                <Option name="offset" value="0" type="QString"/>
                <Option name="offset_along_line" value="0" type="QString"/>
                <Option name="offset_along_line_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_along_line_unit" value="MM" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="place_on_every_part" value="true" type="bool"/>
                <Option name="placements" value="CentralPoint" type="QString"/>
                <Option name="ring_filter" value="0" type="QString"/>
                <Option name="rotate" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties"/>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
              <symbol name="@@3@0@0" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="marker" frame_rate="10">
                <data_defined_properties>
                  <Option type="Map">
                    <Option name="name" value="" type="QString"/>
                    <Option name="properties"/>
                    <Option name="type" value="collection" type="QString"/>
                  </Option>
                </data_defined_properties>
                <layer id="{a673d31b-f0f0-4cbf-8eef-04c02fe3fe37}" locked="0" pass="0" enabled="1" class="FontMarker">
                  <Option type="Map">
                    <Option name="angle" value="0" type="QString"/>
                    <Option name="chr" value="A" type="QString"/>
                    <Option name="color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                    <Option name="font" value="Arial" type="QString"/>
                    <Option name="font_style" value="Normal" type="QString"/>
                    <Option name="horizontal_anchor_point" value="1" type="QString"/>
                    <Option name="joinstyle" value="miter" type="QString"/>
                    <Option name="offset" value="0,0" type="QString"/>
                    <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="offset_unit" value="MapUnit" type="QString"/>
                    <Option name="outline_color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                    <Option name="outline_width" value="20" type="QString"/>
                    <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                    <Option name="size" value="150" type="QString"/>
                    <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="size_unit" value="MapUnit" type="QString"/>
                    <Option name="vertical_anchor_point" value="1" type="QString"/>
                  </Option>
                  <data_defined_properties>
                    <Option type="Map">
                      <Option name="name" value="" type="QString"/>
                      <Option name="properties" type="Map">
                        <Option name="char" type="Map">
                          <Option name="active" value="true" type="bool"/>
                          <Option name="expression" value="CASE&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 4 THEN 'I I'&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 3 THEN 'X'&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 5 THEN 'I'&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 2 THEN 'X X'&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 7 THEN 'I I I'&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 1 THEN 'X X X'&#xd;&#xa;END" type="QString"/>
                          <Option name="type" value="3" type="int"/>
                        </Option>
                        <Option name="size" type="Map">
                          <Option name="active" value="true" type="bool"/>
                          <Option name="expression" value="&quot;borda&quot;" type="QString"/>
                          <Option name="type" value="3" type="int"/>
                        </Option>
                      </Option>
                      <Option name="type" value="collection" type="QString"/>
                    </Option>
                  </data_defined_properties>
                </layer>
                <layer id="{44868964-7155-4e93-8745-6f1d21fc272e}" locked="0" pass="0" enabled="1" class="FontMarker">
                  <Option type="Map">
                    <Option name="angle" value="0" type="QString"/>
                    <Option name="chr" value="A" type="QString"/>
                    <Option name="color" value="0,0,0,255,rgb:0,0,0,1" type="QString"/>
                    <Option name="font" value="Arial" type="QString"/>
                    <Option name="font_style" value="Normal" type="QString"/>
                    <Option name="horizontal_anchor_point" value="1" type="QString"/>
                    <Option name="joinstyle" value="miter" type="QString"/>
                    <Option name="offset" value="0,0" type="QString"/>
                    <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="offset_unit" value="MapUnit" type="QString"/>
                    <Option name="outline_color" value="35,35,35,255,rgb:0.13725490196078433,0.13725490196078433,0.13725490196078433,1" type="QString"/>
                    <Option name="outline_width" value="20" type="QString"/>
                    <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                    <Option name="size" value="150" type="QString"/>
                    <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="size_unit" value="MapUnit" type="QString"/>
                    <Option name="vertical_anchor_point" value="1" type="QString"/>
                  </Option>
                  <data_defined_properties>
                    <Option type="Map">
                      <Option name="name" value="" type="QString"/>
                      <Option name="properties" type="Map">
                        <Option name="char" type="Map">
                          <Option name="active" value="true" type="bool"/>
                          <Option name="expression" value="CASE&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 4 THEN 'I I'&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 3 THEN 'X'&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 5 THEN 'I'&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 2 THEN 'X X'&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 7 THEN 'I I I'&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 1 THEN 'X X X'&#xd;&#xa;END" type="QString"/>
                          <Option name="type" value="3" type="int"/>
                        </Option>
                      </Option>
                      <Option name="type" value="collection" type="QString"/>
                    </Option>
                  </data_defined_properties>
                </layer>
              </symbol>
            </layer>
          </symbol>
        </layer>
      </symbol>
      <symbol name="4" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="line" frame_rate="10">
        <data_defined_properties>
          <Option type="Map">
            <Option name="name" value="" type="QString"/>
            <Option name="properties"/>
            <Option name="type" value="collection" type="QString"/>
          </Option>
        </data_defined_properties>
        <layer id="{095572af-69d0-4a92-aa27-4f4eac853fea}" locked="0" pass="0" enabled="1" class="GeometryGenerator">
          <Option type="Map">
            <Option name="SymbolType" value="Marker" type="QString"/>
            <Option name="geometryModifier" value="line_interpolate_point($geometry, length ($geometry)/2+700) " type="QString"/>
            <Option name="units" value="MapUnit" type="QString"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties"/>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </data_defined_properties>
          <symbol name="@4@0" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="marker" frame_rate="10">
            <data_defined_properties>
              <Option type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties" type="Map">
                  <Option name="alpha" type="Map">
                    <Option name="active" value="true" type="bool"/>
                    <Option name="expression" value="if(&quot;tropa_dir&quot; = 6, 100, 0)" type="QString"/>
                    <Option name="type" value="3" type="int"/>
                  </Option>
                </Option>
                <Option name="type" value="collection" type="QString"/>
              </Option>
            </data_defined_properties>
            <layer id="{c4195885-cddf-4b17-b5ff-bd6aa210eef7}" locked="0" pass="0" enabled="1" class="SimpleMarker">
              <Option type="Map">
                <Option name="angle" value="0" type="QString"/>
                <Option name="cap_style" value="square" type="QString"/>
                <Option name="color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                <Option name="horizontal_anchor_point" value="1" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="name" value="circle" type="QString"/>
                <Option name="offset" value="0,0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="outline_color" value="255,255,255,0,rgb:1,1,1,0" type="QString"/>
                <Option name="outline_style" value="solid" type="QString"/>
                <Option name="outline_width" value="0.0001" type="QString"/>
                <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                <Option name="scale_method" value="diameter" type="QString"/>
                <Option name="size" value="150" type="QString"/>
                <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="size_unit" value="MapUnit" type="QString"/>
                <Option name="vertical_anchor_point" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties" type="Map">
                    <Option name="angle" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value=" &quot;Rot_ESQ&quot; " type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="outlineWidth" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="&quot;Borda&quot; *0.3" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="size" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="130  +  &quot;Borda&quot;" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                  </Option>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
            <layer id="{3d80a4a3-ec8a-4e69-a6f3-d2b75b26eff9}" locked="0" pass="0" enabled="1" class="SimpleMarker">
              <Option type="Map">
                <Option name="angle" value="0" type="QString"/>
                <Option name="cap_style" value="square" type="QString"/>
                <Option name="color" value="0,0,0,255,rgb:0,0,0,1" type="QString"/>
                <Option name="horizontal_anchor_point" value="1" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="name" value="circle" type="QString"/>
                <Option name="offset" value="0,0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="outline_color" value="255,255,255,0,rgb:1,1,1,0" type="QString"/>
                <Option name="outline_style" value="solid" type="QString"/>
                <Option name="outline_width" value="0.0001" type="QString"/>
                <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                <Option name="scale_method" value="diameter" type="QString"/>
                <Option name="size" value="150" type="QString"/>
                <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="size_unit" value="MapUnit" type="QString"/>
                <Option name="vertical_anchor_point" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties" type="Map">
                    <Option name="angle" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value=" &quot;Rot_ESQ&quot; " type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="outlineWidth" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="&quot;Borda&quot; *0.3" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                  </Option>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
          </symbol>
        </layer>
        <layer id="{f7042ced-8951-413c-b4db-c0d12bc20b43}" locked="0" pass="0" enabled="1" class="GeometryGenerator">
          <Option type="Map">
            <Option name="SymbolType" value="Marker" type="QString"/>
            <Option name="geometryModifier" value="line_interpolate_point($geometry, length ($geometry)/2+500) " type="QString"/>
            <Option name="units" value="MapUnit" type="QString"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties"/>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </data_defined_properties>
          <symbol name="@4@1" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="marker" frame_rate="10">
            <data_defined_properties>
              <Option type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties" type="Map">
                  <Option name="alpha" type="Map">
                    <Option name="active" value="true" type="bool"/>
                    <Option name="expression" value="if(&quot;tropa_dir&quot; = 6, 100, 0)" type="QString"/>
                    <Option name="type" value="3" type="int"/>
                  </Option>
                </Option>
                <Option name="type" value="collection" type="QString"/>
              </Option>
            </data_defined_properties>
            <layer id="{2e905138-ad57-45a9-a136-6e4ac8803e7c}" locked="0" pass="0" enabled="1" class="SimpleMarker">
              <Option type="Map">
                <Option name="angle" value="0" type="QString"/>
                <Option name="cap_style" value="square" type="QString"/>
                <Option name="color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                <Option name="horizontal_anchor_point" value="1" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="name" value="circle" type="QString"/>
                <Option name="offset" value="0,0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="outline_color" value="255,255,255,0,rgb:1,1,1,0" type="QString"/>
                <Option name="outline_style" value="solid" type="QString"/>
                <Option name="outline_width" value="0.0001" type="QString"/>
                <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                <Option name="scale_method" value="diameter" type="QString"/>
                <Option name="size" value="150" type="QString"/>
                <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="size_unit" value="MapUnit" type="QString"/>
                <Option name="vertical_anchor_point" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties" type="Map">
                    <Option name="angle" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value=" &quot;Rot_ESQ&quot; " type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="outlineWidth" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="&quot;Borda&quot; *0.3" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="size" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="130  +  &quot;Borda&quot;" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                  </Option>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
            <layer id="{caa530bd-992c-4412-950b-179712218bed}" locked="0" pass="0" enabled="1" class="SimpleMarker">
              <Option type="Map">
                <Option name="angle" value="0" type="QString"/>
                <Option name="cap_style" value="square" type="QString"/>
                <Option name="color" value="0,0,0,255,rgb:0,0,0,1" type="QString"/>
                <Option name="horizontal_anchor_point" value="1" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="name" value="circle" type="QString"/>
                <Option name="offset" value="0,0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="outline_color" value="255,255,255,0,rgb:1,1,1,0" type="QString"/>
                <Option name="outline_style" value="solid" type="QString"/>
                <Option name="outline_width" value="0.0001" type="QString"/>
                <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                <Option name="scale_method" value="diameter" type="QString"/>
                <Option name="size" value="150" type="QString"/>
                <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="size_unit" value="MapUnit" type="QString"/>
                <Option name="vertical_anchor_point" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties" type="Map">
                    <Option name="angle" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value=" &quot;Rot_ESQ&quot; " type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="outlineWidth" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="&quot;Borda&quot; *0.3" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                  </Option>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
          </symbol>
        </layer>
        <layer id="{d182b9cf-dfcf-47e3-8420-39effc35eb78}" locked="0" pass="0" enabled="1" class="GeometryGenerator">
          <Option type="Map">
            <Option name="SymbolType" value="Marker" type="QString"/>
            <Option name="geometryModifier" value="line_interpolate_point($geometry, length ($geometry)/2+300) " type="QString"/>
            <Option name="units" value="MapUnit" type="QString"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties"/>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </data_defined_properties>
          <symbol name="@4@2" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="marker" frame_rate="10">
            <data_defined_properties>
              <Option type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties" type="Map">
                  <Option name="alpha" type="Map">
                    <Option name="active" value="true" type="bool"/>
                    <Option name="expression" value="if(&quot;tropa_dir&quot; = 6, 100, 0)" type="QString"/>
                    <Option name="type" value="3" type="int"/>
                  </Option>
                </Option>
                <Option name="type" value="collection" type="QString"/>
              </Option>
            </data_defined_properties>
            <layer id="{b9514678-2dd4-4247-92f1-0aac09541e6f}" locked="0" pass="0" enabled="1" class="SimpleMarker">
              <Option type="Map">
                <Option name="angle" value="0" type="QString"/>
                <Option name="cap_style" value="square" type="QString"/>
                <Option name="color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                <Option name="horizontal_anchor_point" value="1" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="name" value="circle" type="QString"/>
                <Option name="offset" value="0,0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="outline_color" value="255,255,255,0,rgb:1,1,1,0" type="QString"/>
                <Option name="outline_style" value="solid" type="QString"/>
                <Option name="outline_width" value="0.0001" type="QString"/>
                <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                <Option name="scale_method" value="diameter" type="QString"/>
                <Option name="size" value="150" type="QString"/>
                <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="size_unit" value="MapUnit" type="QString"/>
                <Option name="vertical_anchor_point" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties" type="Map">
                    <Option name="angle" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value=" &quot;Rot_ESQ&quot; " type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="outlineWidth" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="&quot;Borda&quot; *0.3" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="size" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="130  +  &quot;Borda&quot;" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                  </Option>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
            <layer id="{65b5100f-b7cf-4c4d-b583-71c2abd0aec4}" locked="0" pass="0" enabled="1" class="SimpleMarker">
              <Option type="Map">
                <Option name="angle" value="0" type="QString"/>
                <Option name="cap_style" value="square" type="QString"/>
                <Option name="color" value="0,0,0,255,rgb:0,0,0,1" type="QString"/>
                <Option name="horizontal_anchor_point" value="1" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="name" value="circle" type="QString"/>
                <Option name="offset" value="0,0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="outline_color" value="255,255,255,0,rgb:1,1,1,0" type="QString"/>
                <Option name="outline_style" value="solid" type="QString"/>
                <Option name="outline_width" value="0.0001" type="QString"/>
                <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                <Option name="scale_method" value="diameter" type="QString"/>
                <Option name="size" value="150" type="QString"/>
                <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="size_unit" value="MapUnit" type="QString"/>
                <Option name="vertical_anchor_point" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties" type="Map">
                    <Option name="angle" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value=" &quot;Rot_ESQ&quot; " type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="outlineWidth" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="&quot;Borda&quot; *0.3" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                  </Option>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
          </symbol>
        </layer>
        <layer id="{3f440a90-6156-4e8a-a139-01e3c1606b96}" locked="0" pass="0" enabled="1" class="GeometryGenerator">
          <Option type="Map">
            <Option name="SymbolType" value="Marker" type="QString"/>
            <Option name="geometryModifier" value="line_interpolate_point($geometry, length ($geometry)/2-700) " type="QString"/>
            <Option name="units" value="MapUnit" type="QString"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties"/>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </data_defined_properties>
          <symbol name="@4@3" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="marker" frame_rate="10">
            <data_defined_properties>
              <Option type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties" type="Map">
                  <Option name="alpha" type="Map">
                    <Option name="active" value="true" type="bool"/>
                    <Option name="expression" value="if(&quot;tropa_esq&quot; = 6, 100, 0)" type="QString"/>
                    <Option name="type" value="3" type="int"/>
                  </Option>
                </Option>
                <Option name="type" value="collection" type="QString"/>
              </Option>
            </data_defined_properties>
            <layer id="{ea8bb47e-6c13-414c-b5fc-e323d4e5be61}" locked="0" pass="0" enabled="1" class="SimpleMarker">
              <Option type="Map">
                <Option name="angle" value="0" type="QString"/>
                <Option name="cap_style" value="square" type="QString"/>
                <Option name="color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                <Option name="horizontal_anchor_point" value="1" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="name" value="circle" type="QString"/>
                <Option name="offset" value="0,0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="outline_color" value="255,255,255,0,rgb:1,1,1,0" type="QString"/>
                <Option name="outline_style" value="solid" type="QString"/>
                <Option name="outline_width" value="0.0001" type="QString"/>
                <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                <Option name="scale_method" value="diameter" type="QString"/>
                <Option name="size" value="150" type="QString"/>
                <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="size_unit" value="MapUnit" type="QString"/>
                <Option name="vertical_anchor_point" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties" type="Map">
                    <Option name="angle" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value=" &quot;Rot_ESQ&quot; " type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="outlineWidth" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="&quot;Borda&quot; *0.3" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="size" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="130  +  &quot;Borda&quot;" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                  </Option>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
            <layer id="{fea0be98-8bc0-4654-b240-1ec3e4400663}" locked="0" pass="0" enabled="1" class="SimpleMarker">
              <Option type="Map">
                <Option name="angle" value="0" type="QString"/>
                <Option name="cap_style" value="square" type="QString"/>
                <Option name="color" value="0,0,0,255,rgb:0,0,0,1" type="QString"/>
                <Option name="horizontal_anchor_point" value="1" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="name" value="circle" type="QString"/>
                <Option name="offset" value="0,0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="outline_color" value="255,255,255,0,rgb:1,1,1,0" type="QString"/>
                <Option name="outline_style" value="solid" type="QString"/>
                <Option name="outline_width" value="0.0001" type="QString"/>
                <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                <Option name="scale_method" value="diameter" type="QString"/>
                <Option name="size" value="150" type="QString"/>
                <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="size_unit" value="MapUnit" type="QString"/>
                <Option name="vertical_anchor_point" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties" type="Map">
                    <Option name="angle" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value=" &quot;Rot_ESQ&quot; " type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="outlineWidth" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="&quot;Borda&quot; *0.3" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                  </Option>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
          </symbol>
        </layer>
        <layer id="{a76bba39-6c2b-4d24-8cae-7699418a2895}" locked="0" pass="0" enabled="1" class="GeometryGenerator">
          <Option type="Map">
            <Option name="SymbolType" value="Marker" type="QString"/>
            <Option name="geometryModifier" value="line_interpolate_point($geometry, length ($geometry)/2-500) " type="QString"/>
            <Option name="units" value="MapUnit" type="QString"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties"/>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </data_defined_properties>
          <symbol name="@4@4" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="marker" frame_rate="10">
            <data_defined_properties>
              <Option type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties" type="Map">
                  <Option name="alpha" type="Map">
                    <Option name="active" value="true" type="bool"/>
                    <Option name="expression" value="if(&quot;tropa_esq&quot; = 6, 100, 0)" type="QString"/>
                    <Option name="type" value="3" type="int"/>
                  </Option>
                </Option>
                <Option name="type" value="collection" type="QString"/>
              </Option>
            </data_defined_properties>
            <layer id="{7f3b5b37-583f-4d81-a5ff-7730851d1d0d}" locked="0" pass="0" enabled="1" class="SimpleMarker">
              <Option type="Map">
                <Option name="angle" value="0" type="QString"/>
                <Option name="cap_style" value="square" type="QString"/>
                <Option name="color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                <Option name="horizontal_anchor_point" value="1" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="name" value="circle" type="QString"/>
                <Option name="offset" value="0,0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="outline_color" value="255,255,255,0,rgb:1,1,1,0" type="QString"/>
                <Option name="outline_style" value="solid" type="QString"/>
                <Option name="outline_width" value="0.0001" type="QString"/>
                <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                <Option name="scale_method" value="diameter" type="QString"/>
                <Option name="size" value="150" type="QString"/>
                <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="size_unit" value="MapUnit" type="QString"/>
                <Option name="vertical_anchor_point" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties" type="Map">
                    <Option name="angle" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value=" &quot;Rot_ESQ&quot; " type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="outlineWidth" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="&quot;Borda&quot; *0.3" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="size" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="130  +  &quot;Borda&quot;" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                  </Option>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
            <layer id="{01e94879-632e-4547-b938-059554e524dd}" locked="0" pass="0" enabled="1" class="SimpleMarker">
              <Option type="Map">
                <Option name="angle" value="0" type="QString"/>
                <Option name="cap_style" value="square" type="QString"/>
                <Option name="color" value="0,0,0,255,rgb:0,0,0,1" type="QString"/>
                <Option name="horizontal_anchor_point" value="1" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="name" value="circle" type="QString"/>
                <Option name="offset" value="0,0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="outline_color" value="255,255,255,0,rgb:1,1,1,0" type="QString"/>
                <Option name="outline_style" value="solid" type="QString"/>
                <Option name="outline_width" value="0.0001" type="QString"/>
                <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                <Option name="scale_method" value="diameter" type="QString"/>
                <Option name="size" value="150" type="QString"/>
                <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="size_unit" value="MapUnit" type="QString"/>
                <Option name="vertical_anchor_point" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties" type="Map">
                    <Option name="angle" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value=" &quot;Rot_ESQ&quot; " type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="outlineWidth" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="&quot;Borda&quot; *0.3" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                  </Option>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
          </symbol>
        </layer>
        <layer id="{ba9268c8-47dd-4e8a-918d-83c7663aa586}" locked="0" pass="0" enabled="1" class="GeometryGenerator">
          <Option type="Map">
            <Option name="SymbolType" value="Marker" type="QString"/>
            <Option name="geometryModifier" value="line_interpolate_point($geometry, length ($geometry)/2-300) " type="QString"/>
            <Option name="units" value="MapUnit" type="QString"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties"/>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </data_defined_properties>
          <symbol name="@4@5" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="marker" frame_rate="10">
            <data_defined_properties>
              <Option type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties" type="Map">
                  <Option name="alpha" type="Map">
                    <Option name="active" value="true" type="bool"/>
                    <Option name="expression" value="if(&quot;tropa_esq&quot; = 6, 100, 0)" type="QString"/>
                    <Option name="type" value="3" type="int"/>
                  </Option>
                </Option>
                <Option name="type" value="collection" type="QString"/>
              </Option>
            </data_defined_properties>
            <layer id="{e5888bed-f214-4f2f-ae4c-09d7a1af2f77}" locked="0" pass="0" enabled="1" class="SimpleMarker">
              <Option type="Map">
                <Option name="angle" value="0" type="QString"/>
                <Option name="cap_style" value="square" type="QString"/>
                <Option name="color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                <Option name="horizontal_anchor_point" value="1" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="name" value="circle" type="QString"/>
                <Option name="offset" value="0,0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="outline_color" value="255,255,255,0,rgb:1,1,1,0" type="QString"/>
                <Option name="outline_style" value="solid" type="QString"/>
                <Option name="outline_width" value="0.0001" type="QString"/>
                <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                <Option name="scale_method" value="diameter" type="QString"/>
                <Option name="size" value="150" type="QString"/>
                <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="size_unit" value="MapUnit" type="QString"/>
                <Option name="vertical_anchor_point" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties" type="Map">
                    <Option name="angle" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value=" &quot;Rot_ESQ&quot; " type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="outlineWidth" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="0.3* &quot;Borda&quot;" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="size" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="130  +  &quot;Borda&quot;" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                  </Option>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
            <layer id="{9fd40862-fffa-4b7e-beb4-7b4fded255c3}" locked="0" pass="0" enabled="1" class="SimpleMarker">
              <Option type="Map">
                <Option name="angle" value="0" type="QString"/>
                <Option name="cap_style" value="square" type="QString"/>
                <Option name="color" value="0,0,0,255,rgb:0,0,0,1" type="QString"/>
                <Option name="horizontal_anchor_point" value="1" type="QString"/>
                <Option name="joinstyle" value="bevel" type="QString"/>
                <Option name="name" value="circle" type="QString"/>
                <Option name="offset" value="0,0" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="outline_color" value="255,255,255,0,rgb:1,1,1,0" type="QString"/>
                <Option name="outline_style" value="solid" type="QString"/>
                <Option name="outline_width" value="0.0001" type="QString"/>
                <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                <Option name="scale_method" value="diameter" type="QString"/>
                <Option name="size" value="150" type="QString"/>
                <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="size_unit" value="MapUnit" type="QString"/>
                <Option name="vertical_anchor_point" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties" type="Map">
                    <Option name="angle" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value=" &quot;Rot_ESQ&quot; " type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                    <Option name="outlineWidth" type="Map">
                      <Option name="active" value="true" type="bool"/>
                      <Option name="expression" value="0.3* &quot;Borda&quot;" type="QString"/>
                      <Option name="type" value="3" type="int"/>
                    </Option>
                  </Option>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
          </symbol>
        </layer>
      </symbol>
      <symbol name="5" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="line" frame_rate="10">
        <data_defined_properties>
          <Option type="Map">
            <Option name="name" value="" type="QString"/>
            <Option name="properties"/>
            <Option name="type" value="collection" type="QString"/>
          </Option>
        </data_defined_properties>
        <layer id="{d34eca90-1e9a-4328-b698-aff94e83481a}" locked="0" pass="0" enabled="1" class="GeometryGenerator">
          <Option type="Map">
            <Option name="SymbolType" value="Line" type="QString"/>
            <Option name="geometryModifier" value="make_line(&#xd;&#xa;line_interpolate_point($geometry, length ($geometry)/2-700),&#xd;&#xa;line_interpolate_point($geometry, length ($geometry)/2-300)&#xd;&#xa;) " type="QString"/>
            <Option name="units" value="MapUnit" type="QString"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties"/>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </data_defined_properties>
          <symbol name="@5@0" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="line" frame_rate="10">
            <data_defined_properties>
              <Option type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties"/>
                <Option name="type" value="collection" type="QString"/>
              </Option>
            </data_defined_properties>
            <layer id="{da0c1276-13e5-4c4e-b0ff-4c4f9e84fe59}" locked="0" pass="0" enabled="1" class="MarkerLine">
              <Option type="Map">
                <Option name="average_angle_length" value="0" type="QString"/>
                <Option name="average_angle_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="average_angle_unit" value="MapUnit" type="QString"/>
                <Option name="interval" value="3" type="QString"/>
                <Option name="interval_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="interval_unit" value="MM" type="QString"/>
                <Option name="offset" value="0" type="QString"/>
                <Option name="offset_along_line" value="0" type="QString"/>
                <Option name="offset_along_line_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_along_line_unit" value="MM" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="place_on_every_part" value="true" type="bool"/>
                <Option name="placements" value="CentralPoint" type="QString"/>
                <Option name="ring_filter" value="0" type="QString"/>
                <Option name="rotate" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties"/>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
              <symbol name="@@5@0@0" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="marker" frame_rate="10">
                <data_defined_properties>
                  <Option type="Map">
                    <Option name="name" value="" type="QString"/>
                    <Option name="properties"/>
                    <Option name="type" value="collection" type="QString"/>
                  </Option>
                </data_defined_properties>
                <layer id="{ed6e0cde-0d49-4353-be59-e20f19afe6e4}" locked="0" pass="0" enabled="1" class="FontMarker">
                  <Option type="Map">
                    <Option name="angle" value="0" type="QString"/>
                    <Option name="chr" value="A" type="QString"/>
                    <Option name="color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                    <Option name="font" value="Arial" type="QString"/>
                    <Option name="font_style" value="Normal" type="QString"/>
                    <Option name="horizontal_anchor_point" value="1" type="QString"/>
                    <Option name="joinstyle" value="miter" type="QString"/>
                    <Option name="offset" value="0,0" type="QString"/>
                    <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="offset_unit" value="MapUnit" type="QString"/>
                    <Option name="outline_color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                    <Option name="outline_width" value="20" type="QString"/>
                    <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                    <Option name="size" value="150" type="QString"/>
                    <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="size_unit" value="MapUnit" type="QString"/>
                    <Option name="vertical_anchor_point" value="1" type="QString"/>
                  </Option>
                  <data_defined_properties>
                    <Option type="Map">
                      <Option name="name" value="" type="QString"/>
                      <Option name="properties" type="Map">
                        <Option name="char" type="Map">
                          <Option name="active" value="true" type="bool"/>
                          <Option name="expression" value="CASE&#xd;&#xa;&#x9;WHEN &quot;tropa_esq&quot; = 4 THEN 'I I'&#xd;&#xa;&#x9;WHEN &quot;tropa_esq&quot; = 3 THEN 'X'&#xd;&#xa;&#x9;WHEN &quot;tropa_esq&quot; = 5 THEN 'I'&#xd;&#xa;&#x9;WHEN &quot;tropa_esq&quot; = 2 THEN 'X X'&#xd;&#xa;&#x9;WHEN &quot;tropa_esq&quot; = 7 THEN 'I I I'&#xd;&#xa;&#x9;WHEN &quot;tropa_esq&quot; = 1 THEN 'X X X'&#xd;&#xa;END" type="QString"/>
                          <Option name="type" value="3" type="int"/>
                        </Option>
                        <Option name="size" type="Map">
                          <Option name="active" value="true" type="bool"/>
                          <Option name="expression" value="&quot;borda&quot;" type="QString"/>
                          <Option name="type" value="3" type="int"/>
                        </Option>
                      </Option>
                      <Option name="type" value="collection" type="QString"/>
                    </Option>
                  </data_defined_properties>
                </layer>
                <layer id="{af95fe13-5d84-4959-86da-883c1b45f097}" locked="0" pass="0" enabled="1" class="FontMarker">
                  <Option type="Map">
                    <Option name="angle" value="0" type="QString"/>
                    <Option name="chr" value="A" type="QString"/>
                    <Option name="color" value="0,0,0,255,rgb:0,0,0,1" type="QString"/>
                    <Option name="font" value="Arial" type="QString"/>
                    <Option name="font_style" value="Normal" type="QString"/>
                    <Option name="horizontal_anchor_point" value="1" type="QString"/>
                    <Option name="joinstyle" value="miter" type="QString"/>
                    <Option name="offset" value="0,0" type="QString"/>
                    <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="offset_unit" value="MapUnit" type="QString"/>
                    <Option name="outline_color" value="35,35,35,255,rgb:0.13725490196078433,0.13725490196078433,0.13725490196078433,1" type="QString"/>
                    <Option name="outline_width" value="20" type="QString"/>
                    <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                    <Option name="size" value="150" type="QString"/>
                    <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="size_unit" value="MapUnit" type="QString"/>
                    <Option name="vertical_anchor_point" value="1" type="QString"/>
                  </Option>
                  <data_defined_properties>
                    <Option type="Map">
                      <Option name="name" value="" type="QString"/>
                      <Option name="properties" type="Map">
                        <Option name="char" type="Map">
                          <Option name="active" value="true" type="bool"/>
                          <Option name="expression" value="CASE&#xd;&#xa;&#x9;WHEN &quot;tropa_esq&quot; = 4 THEN 'I I'&#xd;&#xa;&#x9;WHEN &quot;tropa_esq&quot; = 3 THEN 'X'&#xd;&#xa;&#x9;WHEN &quot;tropa_esq&quot; = 5 THEN 'I'&#xd;&#xa;&#x9;WHEN &quot;tropa_esq&quot; = 2 THEN 'X X'&#xd;&#xa;&#x9;WHEN &quot;tropa_esq&quot; = 7 THEN 'I I I'&#xd;&#xa;&#x9;WHEN &quot;tropa_esq&quot; = 1 THEN 'X X X'&#xd;&#xa;END" type="QString"/>
                          <Option name="type" value="3" type="int"/>
                        </Option>
                      </Option>
                      <Option name="type" value="collection" type="QString"/>
                    </Option>
                  </data_defined_properties>
                </layer>
              </symbol>
            </layer>
          </symbol>
        </layer>
        <layer id="{57e41407-ed5b-4ceb-9ba0-faaa95b0bcfc}" locked="0" pass="0" enabled="1" class="GeometryGenerator">
          <Option type="Map">
            <Option name="SymbolType" value="Line" type="QString"/>
            <Option name="geometryModifier" value="make_line(&#xd;&#xa;line_interpolate_point($geometry, length ($geometry)/2+700),&#xd;&#xa;line_interpolate_point($geometry, length ($geometry)/2+300)&#xd;&#xa;) " type="QString"/>
            <Option name="units" value="MapUnit" type="QString"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties"/>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </data_defined_properties>
          <symbol name="@5@1" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="line" frame_rate="10">
            <data_defined_properties>
              <Option type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties"/>
                <Option name="type" value="collection" type="QString"/>
              </Option>
            </data_defined_properties>
            <layer id="{ff654388-7209-46b6-b44e-fba0c46952c5}" locked="0" pass="0" enabled="1" class="MarkerLine">
              <Option type="Map">
                <Option name="average_angle_length" value="0" type="QString"/>
                <Option name="average_angle_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="average_angle_unit" value="MapUnit" type="QString"/>
                <Option name="interval" value="3" type="QString"/>
                <Option name="interval_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="interval_unit" value="MM" type="QString"/>
                <Option name="offset" value="0" type="QString"/>
                <Option name="offset_along_line" value="0" type="QString"/>
                <Option name="offset_along_line_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_along_line_unit" value="MM" type="QString"/>
                <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                <Option name="offset_unit" value="MapUnit" type="QString"/>
                <Option name="place_on_every_part" value="true" type="bool"/>
                <Option name="placements" value="CentralPoint" type="QString"/>
                <Option name="ring_filter" value="0" type="QString"/>
                <Option name="rotate" value="1" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option name="name" value="" type="QString"/>
                  <Option name="properties"/>
                  <Option name="type" value="collection" type="QString"/>
                </Option>
              </data_defined_properties>
              <symbol name="@@5@1@0" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="marker" frame_rate="10">
                <data_defined_properties>
                  <Option type="Map">
                    <Option name="name" value="" type="QString"/>
                    <Option name="properties"/>
                    <Option name="type" value="collection" type="QString"/>
                  </Option>
                </data_defined_properties>
                <layer id="{f43fc3c4-192c-4600-a19a-a69477dcf8ab}" locked="0" pass="0" enabled="1" class="FontMarker">
                  <Option type="Map">
                    <Option name="angle" value="0" type="QString"/>
                    <Option name="chr" value="A" type="QString"/>
                    <Option name="color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                    <Option name="font" value="Arial" type="QString"/>
                    <Option name="font_style" value="Normal" type="QString"/>
                    <Option name="horizontal_anchor_point" value="1" type="QString"/>
                    <Option name="joinstyle" value="miter" type="QString"/>
                    <Option name="offset" value="0,0" type="QString"/>
                    <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="offset_unit" value="MapUnit" type="QString"/>
                    <Option name="outline_color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                    <Option name="outline_width" value="20" type="QString"/>
                    <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                    <Option name="size" value="150" type="QString"/>
                    <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="size_unit" value="MapUnit" type="QString"/>
                    <Option name="vertical_anchor_point" value="1" type="QString"/>
                  </Option>
                  <data_defined_properties>
                    <Option type="Map">
                      <Option name="name" value="" type="QString"/>
                      <Option name="properties" type="Map">
                        <Option name="char" type="Map">
                          <Option name="active" value="true" type="bool"/>
                          <Option name="expression" value="CASE&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 4 THEN 'I I'&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 3 THEN 'X'&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 5 THEN 'I'&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 2 THEN 'X X'&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 7 THEN 'I I I'&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 1 THEN 'X X X'&#xd;&#xa;END" type="QString"/>
                          <Option name="type" value="3" type="int"/>
                        </Option>
                        <Option name="size" type="Map">
                          <Option name="active" value="true" type="bool"/>
                          <Option name="expression" value="&quot;borda&quot;" type="QString"/>
                          <Option name="type" value="3" type="int"/>
                        </Option>
                      </Option>
                      <Option name="type" value="collection" type="QString"/>
                    </Option>
                  </data_defined_properties>
                </layer>
                <layer id="{154ebca2-71a3-444a-a233-133c6b08b59b}" locked="0" pass="0" enabled="1" class="FontMarker">
                  <Option type="Map">
                    <Option name="angle" value="0" type="QString"/>
                    <Option name="chr" value="A" type="QString"/>
                    <Option name="color" value="0,0,0,255,rgb:0,0,0,1" type="QString"/>
                    <Option name="font" value="Arial" type="QString"/>
                    <Option name="font_style" value="Normal" type="QString"/>
                    <Option name="horizontal_anchor_point" value="1" type="QString"/>
                    <Option name="joinstyle" value="miter" type="QString"/>
                    <Option name="offset" value="0,0" type="QString"/>
                    <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="offset_unit" value="MapUnit" type="QString"/>
                    <Option name="outline_color" value="35,35,35,255,rgb:0.13725490196078433,0.13725490196078433,0.13725490196078433,1" type="QString"/>
                    <Option name="outline_width" value="20" type="QString"/>
                    <Option name="outline_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="outline_width_unit" value="MapUnit" type="QString"/>
                    <Option name="size" value="150" type="QString"/>
                    <Option name="size_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="size_unit" value="MapUnit" type="QString"/>
                    <Option name="vertical_anchor_point" value="1" type="QString"/>
                  </Option>
                  <data_defined_properties>
                    <Option type="Map">
                      <Option name="name" value="" type="QString"/>
                      <Option name="properties" type="Map">
                        <Option name="char" type="Map">
                          <Option name="active" value="true" type="bool"/>
                          <Option name="expression" value="CASE&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 4 THEN 'I I'&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 3 THEN 'X'&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 5 THEN 'I'&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 2 THEN 'X X'&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 7 THEN 'I I I'&#xd;&#xa;&#x9;WHEN &quot;tropa_dir&quot; = 1 THEN 'X X X'&#xd;&#xa;END" type="QString"/>
                          <Option name="type" value="3" type="int"/>
                        </Option>
                      </Option>
                      <Option name="type" value="collection" type="QString"/>
                    </Option>
                  </data_defined_properties>
                </layer>
              </symbol>
            </layer>
          </symbol>
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
      <symbol name="" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="line" frame_rate="10">
        <data_defined_properties>
          <Option type="Map">
            <Option name="name" value="" type="QString"/>
            <Option name="properties"/>
            <Option name="type" value="collection" type="QString"/>
          </Option>
        </data_defined_properties>
        <layer id="{7cc7b318-72e1-47fb-a8f2-c1aa588213e1}" locked="0" pass="0" enabled="1" class="SimpleLine">
          <Option type="Map">
            <Option name="align_dash_pattern" value="0" type="QString"/>
            <Option name="capstyle" value="square" type="QString"/>
            <Option name="customdash" value="5;2" type="QString"/>
            <Option name="customdash_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
            <Option name="customdash_unit" value="MM" type="QString"/>
            <Option name="dash_pattern_offset" value="0" type="QString"/>
            <Option name="dash_pattern_offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
            <Option name="dash_pattern_offset_unit" value="MM" type="QString"/>
            <Option name="draw_inside_polygon" value="0" type="QString"/>
            <Option name="joinstyle" value="bevel" type="QString"/>
            <Option name="line_color" value="35,35,35,255,rgb:0.13725490196078433,0.13725490196078433,0.13725490196078433,1" type="QString"/>
            <Option name="line_style" value="solid" type="QString"/>
            <Option name="line_width" value="0.26" type="QString"/>
            <Option name="line_width_unit" value="MM" type="QString"/>
            <Option name="offset" value="0" type="QString"/>
            <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
            <Option name="offset_unit" value="MM" type="QString"/>
            <Option name="ring_filter" value="0" type="QString"/>
            <Option name="trim_distance_end" value="0" type="QString"/>
            <Option name="trim_distance_end_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
            <Option name="trim_distance_end_unit" value="MM" type="QString"/>
            <Option name="trim_distance_start" value="0" type="QString"/>
            <Option name="trim_distance_start_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
            <Option name="trim_distance_start_unit" value="MM" type="QString"/>
            <Option name="tweak_dash_pattern_on_corners" value="0" type="QString"/>
            <Option name="use_custom_dash" value="0" type="QString"/>
            <Option name="width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
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
  <labeling type="rule-based">
    <rules key="{fbf5b50e-fbfe-4c4b-b09f-3801ee496109}">
      <rule description="Nome esquerda igual" key="{6835b2f1-c9ca-4e8f-a3ff-db82ce92e2ee}" filter=" &quot;tropa_esq&quot;  =  &quot;tropa_dir&quot; ">
        <settings calloutType="simple">
          <text-style previewBkgrdColor="255,255,255,255,rgb:1,1,1,1" tabStopDistanceMapUnitScale="3x:0,0,0,0,0,0" textColor="0,0,0,255,rgb:0,0,0,1" multilineHeightUnit="Percentage" fontSizeMapUnitScale="3x:0,0,0,0,0,0" forcedItalic="0" textOrientation="horizontal" blendMode="0" fontSizeUnit="MapUnit" fontLetterSpacing="0" stretchFactor="100" fieldName="nome_esq" fontSize="170" capitalization="0" isExpression="0" namedStyle="Normal" forcedBold="0" useSubstitutions="0" fontKerning="1" fontStrikeout="0" tabStopDistance="80" fontItalic="0" fontWeight="87" allowHtml="0" textOpacity="1" fontWordSpacing="0" legendString="Aa" fontFamily="Arial Black" fontUnderline="0" tabStopDistanceUnit="Point" multilineHeight="2.2999999999999998">
            <families/>
            <text-buffer bufferOpacity="1" bufferSizeUnits="MapUnit" bufferColor="255,255,255,255,rgb:1,1,1,1" bufferDraw="1" bufferBlendMode="0" bufferSize="0.29999999999999999" bufferNoFill="0" bufferSizeMapUnitScale="3x:0,0,0,0,0,0" bufferJoinStyle="128"/>
            <text-mask maskSize2="1.5" maskEnabled="0" maskSizeUnits="MM" maskOpacity="1" maskJoinStyle="128" maskSize="1.5" maskedSymbolLayers="" maskType="0" maskSizeMapUnitScale="3x:0,0,0,0,0,0"/>
            <background shapeOffsetY="0" shapeRadiiMapUnitScale="3x:0,0,0,0,0,0" shapeJoinStyle="64" shapeOffsetUnit="MM" shapeOffsetMapUnitScale="3x:0,0,0,0,0,0" shapeRotationType="0" shapeBlendMode="0" shapeOpacity="1" shapeBorderWidthMapUnitScale="3x:0,0,0,0,0,0" shapeDraw="0" shapeSizeMapUnitScale="3x:0,0,0,0,0,0" shapeSizeType="0" shapeSizeY="0" shapeSVGFile="" shapeRadiiX="0" shapeBorderWidthUnit="MM" shapeRadiiUnit="MM" shapeType="0" shapeOffsetX="0" shapeFillColor="255,255,255,255,rgb:1,1,1,1" shapeSizeX="0" shapeRotation="0" shapeRadiiY="0" shapeBorderWidth="0" shapeBorderColor="128,128,128,255,rgb:0.50196078431372548,0.50196078431372548,0.50196078431372548,1" shapeSizeUnit="MM">
              <symbol name="markerSymbol" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="marker" frame_rate="10">
                <data_defined_properties>
                  <Option type="Map">
                    <Option name="name" value="" type="QString"/>
                    <Option name="properties"/>
                    <Option name="type" value="collection" type="QString"/>
                  </Option>
                </data_defined_properties>
                <layer id="" locked="0" pass="0" enabled="1" class="SimpleMarker">
                  <Option type="Map">
                    <Option name="angle" value="0" type="QString"/>
                    <Option name="cap_style" value="square" type="QString"/>
                    <Option name="color" value="255,158,23,255,rgb:1,0.61960784313725492,0.09019607843137255,1" type="QString"/>
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
              <symbol name="fillSymbol" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="fill" frame_rate="10">
                <data_defined_properties>
                  <Option type="Map">
                    <Option name="name" value="" type="QString"/>
                    <Option name="properties"/>
                    <Option name="type" value="collection" type="QString"/>
                  </Option>
                </data_defined_properties>
                <layer id="" locked="0" pass="0" enabled="1" class="SimpleFill">
                  <Option type="Map">
                    <Option name="border_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                    <Option name="joinstyle" value="bevel" type="QString"/>
                    <Option name="offset" value="0,0" type="QString"/>
                    <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="offset_unit" value="MM" type="QString"/>
                    <Option name="outline_color" value="128,128,128,255,rgb:0.50196078431372548,0.50196078431372548,0.50196078431372548,1" type="QString"/>
                    <Option name="outline_style" value="no" type="QString"/>
                    <Option name="outline_width" value="0" type="QString"/>
                    <Option name="outline_width_unit" value="MM" type="QString"/>
                    <Option name="style" value="solid" type="QString"/>
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
            </background>
            <shadow shadowOffsetMapUnitScale="3x:0,0,0,0,0,0" shadowRadiusUnit="MM" shadowDraw="0" shadowUnder="0" shadowOffsetGlobal="1" shadowOffsetUnit="MM" shadowBlendMode="6" shadowScale="100" shadowRadius="1.5" shadowColor="0,0,0,255,rgb:0,0,0,1" shadowOffsetAngle="135" shadowRadiusAlphaOnly="0" shadowOpacity="0.69999999999999996" shadowOffsetDist="1" shadowRadiusMapUnitScale="3x:0,0,0,0,0,0"/>
            <dd_properties>
              <Option type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties"/>
                <Option name="type" value="collection" type="QString"/>
              </Option>
            </dd_properties>
            <substitutions/>
          </text-style>
          <text-format reverseDirectionSymbol="0" plussign="0" placeDirectionSymbol="0" wrapChar="|" formatNumbers="0" leftDirectionSymbol="&lt;" useMaxLineLengthForAutoWrap="1" addDirectionSymbol="0" autoWrapLength="0" decimals="3" rightDirectionSymbol=">" multilineAlign="1"/>
          <placement maxCurvedCharAngleOut="-25" maximumDistanceMapUnitScale="3x:0,0,0,0,0,0" placementFlags="9" overlapHandling="AllowOverlapIfRequired" prioritization="PreferCloser" overrunDistanceMapUnitScale="3x:0,0,0,0,0,0" fitInPolygonOnly="0" lineAnchorTextPoint="CenterOfText" geometryGenerator="" maximumDistanceUnit="MM" offsetUnits="MapUnit" repeatDistanceUnits="MapUnit" lineAnchorClipping="0" distMapUnitScale="3x:0,0,0,0,0,0" lineAnchorType="0" rotationUnit="AngleDegrees" maxCurvedCharAngleIn="25" overrunDistance="0" polygonPlacementFlags="2" xOffset="0" preserveRotation="1" offsetType="0" lineAnchorPercent="0.5" repeatDistance="0" geometryGeneratorType="PointGeometry" overrunDistanceUnit="MM" layerType="LineGeometry" centroidInside="0" dist="0" distUnits="MM" centroidWhole="0" repeatDistanceMapUnitScale="3x:0,0,0,0,0,0" yOffset="0" placement="4" rotationAngle="0" priority="5" allowDegraded="1" predefinedPositionOrder="TR,TL,BR,BL,R,L,TSR,BSR" maximumDistance="0" labelOffsetMapUnitScale="3x:0,0,0,0,0,0" quadOffset="4" geometryGeneratorEnabled="0"/>
          <rendering scaleVisibility="0" fontMinPixelSize="3" labelPerPart="0" scaleMax="10000000" scaleMin="1" mergeLines="0" limitNumLabels="0" fontMaxPixelSize="10000" minFeatureSize="0" unplacedVisibility="0" maxNumLabels="2000" upsidedownLabels="2" obstacle="0" drawLabels="1" obstacleFactor="1" obstacleType="0" fontLimitPixelSize="0" zIndex="0"/>
          <dd_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties" type="Map">
                <Option name="BufferSize" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="0.45* &quot;Borda&quot;" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="Hali" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="'Center'" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="LabelRotation" type="Map">
                  <Option name="active" value="false" type="bool"/>
                  <Option name="type" value="1" type="int"/>
                  <Option name="val" value="" type="QString"/>
                </Option>
                <Option name="PositionX" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="x(line_interpolate_point($geometry,  length ($geometry)/2))&#xd;&#xa;&#xd;&#xa;+ (200 + 110*(length (&quot;nome_esq&quot;)/2 )) * cos(&#xd;&#xa;&#xd;&#xa;&#xd;&#xa;atan2(  &#xd;&#xa;y( line_interpolate_point($geometry, length ($geometry)/2+1)) &#xd;&#xa;-y(line_interpolate_point($geometry, length ($geometry)/2-1)),&#xd;&#xa;x( line_interpolate_point($geometry, length ($geometry)/2+1)) &#xd;&#xa;-x(line_interpolate_point($geometry, length ($geometry)/2-1))&#xd;&#xa;)&#xd;&#xa;+ pi()/2 &#xd;&#xa;)" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="PositionY" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="y(line_interpolate_point($geometry,  length ($geometry)/2))&#xd;&#xa;&#xd;&#xa;+ 300 * (sin(&#xd;&#xa;&#xd;&#xa;&#xd;&#xa;atan2(  &#xd;&#xa;y( line_interpolate_point($geometry, length ($geometry)/2+1))&#xd;&#xa;-y(line_interpolate_point($geometry, length ($geometry)/2-1)) ,&#xd;&#xa;x( line_interpolate_point($geometry, length ($geometry)/2+1)) &#xd;&#xa;-x(line_interpolate_point($geometry, length ($geometry)/2-1)) )&#xd;&#xa;+ pi()/2 &#xd;&#xa;)&#xd;&#xa;)" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="Size" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="&quot;tamanhoTexto&quot;" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="Vali" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="'half'" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
              </Option>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </dd_properties>
          <callout type="simple">
            <Option type="Map">
              <Option name="anchorPoint" value="pole_of_inaccessibility" type="QString"/>
              <Option name="blendMode" value="0" type="int"/>
              <Option name="ddProperties" type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties"/>
                <Option name="type" value="collection" type="QString"/>
              </Option>
              <Option name="drawToAllParts" value="false" type="bool"/>
              <Option name="enabled" value="0" type="QString"/>
              <Option name="labelAnchorPoint" value="point_on_exterior" type="QString"/>
              <Option name="lineSymbol" value="&lt;symbol name=&quot;symbol&quot; alpha=&quot;1&quot; force_rhr=&quot;0&quot; is_animated=&quot;0&quot; clip_to_extent=&quot;1&quot; type=&quot;line&quot; frame_rate=&quot;10&quot;>&lt;data_defined_properties>&lt;Option type=&quot;Map&quot;>&lt;Option name=&quot;name&quot; value=&quot;&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;properties&quot;/>&lt;Option name=&quot;type&quot; value=&quot;collection&quot; type=&quot;QString&quot;/>&lt;/Option>&lt;/data_defined_properties>&lt;layer id=&quot;{8c839ee7-0633-495d-ba3f-b81151e629bd}&quot; locked=&quot;0&quot; pass=&quot;0&quot; enabled=&quot;1&quot; class=&quot;SimpleLine&quot;>&lt;Option type=&quot;Map&quot;>&lt;Option name=&quot;align_dash_pattern&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;capstyle&quot; value=&quot;square&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;customdash&quot; value=&quot;5;2&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;customdash_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;customdash_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;dash_pattern_offset&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;dash_pattern_offset_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;dash_pattern_offset_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;draw_inside_polygon&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;joinstyle&quot; value=&quot;bevel&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;line_color&quot; value=&quot;60,60,60,255,rgb:0.23529411764705882,0.23529411764705882,0.23529411764705882,1&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;line_style&quot; value=&quot;solid&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;line_width&quot; value=&quot;0.3&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;line_width_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;offset&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;offset_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;offset_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;ring_filter&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_end&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_end_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_end_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_start&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_start_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_start_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;tweak_dash_pattern_on_corners&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;use_custom_dash&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;width_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;/Option>&lt;data_defined_properties>&lt;Option type=&quot;Map&quot;>&lt;Option name=&quot;name&quot; value=&quot;&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;properties&quot;/>&lt;Option name=&quot;type&quot; value=&quot;collection&quot; type=&quot;QString&quot;/>&lt;/Option>&lt;/data_defined_properties>&lt;/layer>&lt;/symbol>" type="QString"/>
              <Option name="minLength" value="0" type="double"/>
              <Option name="minLengthMapUnitScale" value="3x:0,0,0,0,0,0" type="QString"/>
              <Option name="minLengthUnit" value="MM" type="QString"/>
              <Option name="offsetFromAnchor" value="0" type="double"/>
              <Option name="offsetFromAnchorMapUnitScale" value="3x:0,0,0,0,0,0" type="QString"/>
              <Option name="offsetFromAnchorUnit" value="MM" type="QString"/>
              <Option name="offsetFromLabel" value="0" type="double"/>
              <Option name="offsetFromLabelMapUnitScale" value="3x:0,0,0,0,0,0" type="QString"/>
              <Option name="offsetFromLabelUnit" value="MM" type="QString"/>
            </Option>
          </callout>
        </settings>
      </rule>
      <rule description="Nome esquerda" key="{2f113364-0f79-4344-a6c4-de7e420b3806}" filter=" &quot;tropa_esq&quot;  &lt;>  &quot;tropa_dir&quot; ">
        <settings calloutType="simple">
          <text-style previewBkgrdColor="255,255,255,255,rgb:1,1,1,1" tabStopDistanceMapUnitScale="3x:0,0,0,0,0,0" textColor="0,0,0,255,rgb:0,0,0,1" multilineHeightUnit="Percentage" fontSizeMapUnitScale="3x:0,0,0,0,0,0" forcedItalic="0" textOrientation="horizontal" blendMode="0" fontSizeUnit="MapUnit" fontLetterSpacing="0" stretchFactor="100" fieldName="nome_esq" fontSize="170" capitalization="0" isExpression="0" namedStyle="Normal" forcedBold="0" useSubstitutions="0" fontKerning="1" fontStrikeout="0" tabStopDistance="80" fontItalic="0" fontWeight="87" allowHtml="0" textOpacity="1" fontWordSpacing="0" legendString="Aa" fontFamily="Arial Black" fontUnderline="0" tabStopDistanceUnit="Point" multilineHeight="2.2999999999999998">
            <families/>
            <text-buffer bufferOpacity="1" bufferSizeUnits="MapUnit" bufferColor="255,255,255,255,rgb:1,1,1,1" bufferDraw="1" bufferBlendMode="0" bufferSize="0.0001" bufferNoFill="0" bufferSizeMapUnitScale="3x:0,0,0,0,0,0" bufferJoinStyle="128"/>
            <text-mask maskSize2="1.5" maskEnabled="0" maskSizeUnits="MM" maskOpacity="1" maskJoinStyle="128" maskSize="1.5" maskedSymbolLayers="" maskType="0" maskSizeMapUnitScale="3x:0,0,0,0,0,0"/>
            <background shapeOffsetY="0" shapeRadiiMapUnitScale="3x:0,0,0,0,0,0" shapeJoinStyle="64" shapeOffsetUnit="MM" shapeOffsetMapUnitScale="3x:0,0,0,0,0,0" shapeRotationType="0" shapeBlendMode="0" shapeOpacity="1" shapeBorderWidthMapUnitScale="3x:0,0,0,0,0,0" shapeDraw="0" shapeSizeMapUnitScale="3x:0,0,0,0,0,0" shapeSizeType="0" shapeSizeY="0" shapeSVGFile="" shapeRadiiX="0" shapeBorderWidthUnit="MM" shapeRadiiUnit="MM" shapeType="0" shapeOffsetX="0" shapeFillColor="255,255,255,255,rgb:1,1,1,1" shapeSizeX="0" shapeRotation="0" shapeRadiiY="0" shapeBorderWidth="0" shapeBorderColor="128,128,128,255,rgb:0.50196078431372548,0.50196078431372548,0.50196078431372548,1" shapeSizeUnit="MM">
              <symbol name="markerSymbol" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="marker" frame_rate="10">
                <data_defined_properties>
                  <Option type="Map">
                    <Option name="name" value="" type="QString"/>
                    <Option name="properties"/>
                    <Option name="type" value="collection" type="QString"/>
                  </Option>
                </data_defined_properties>
                <layer id="" locked="0" pass="0" enabled="1" class="SimpleMarker">
                  <Option type="Map">
                    <Option name="angle" value="0" type="QString"/>
                    <Option name="cap_style" value="square" type="QString"/>
                    <Option name="color" value="231,113,72,255,rgb:0.90588235294117647,0.44313725490196076,0.28235294117647058,1" type="QString"/>
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
              <symbol name="fillSymbol" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="fill" frame_rate="10">
                <data_defined_properties>
                  <Option type="Map">
                    <Option name="name" value="" type="QString"/>
                    <Option name="properties"/>
                    <Option name="type" value="collection" type="QString"/>
                  </Option>
                </data_defined_properties>
                <layer id="" locked="0" pass="0" enabled="1" class="SimpleFill">
                  <Option type="Map">
                    <Option name="border_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                    <Option name="joinstyle" value="bevel" type="QString"/>
                    <Option name="offset" value="0,0" type="QString"/>
                    <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="offset_unit" value="MM" type="QString"/>
                    <Option name="outline_color" value="128,128,128,255,rgb:0.50196078431372548,0.50196078431372548,0.50196078431372548,1" type="QString"/>
                    <Option name="outline_style" value="no" type="QString"/>
                    <Option name="outline_width" value="0" type="QString"/>
                    <Option name="outline_width_unit" value="MM" type="QString"/>
                    <Option name="style" value="solid" type="QString"/>
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
            </background>
            <shadow shadowOffsetMapUnitScale="3x:0,0,0,0,0,0" shadowRadiusUnit="MM" shadowDraw="0" shadowUnder="0" shadowOffsetGlobal="1" shadowOffsetUnit="MM" shadowBlendMode="6" shadowScale="100" shadowRadius="1.5" shadowColor="0,0,0,255,rgb:0,0,0,1" shadowOffsetAngle="135" shadowRadiusAlphaOnly="0" shadowOpacity="0.69999999999999996" shadowOffsetDist="1" shadowRadiusMapUnitScale="3x:0,0,0,0,0,0"/>
            <dd_properties>
              <Option type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties"/>
                <Option name="type" value="collection" type="QString"/>
              </Option>
            </dd_properties>
            <substitutions/>
          </text-style>
          <text-format reverseDirectionSymbol="0" plussign="0" placeDirectionSymbol="0" wrapChar="|" formatNumbers="0" leftDirectionSymbol="&lt;" useMaxLineLengthForAutoWrap="1" addDirectionSymbol="0" autoWrapLength="0" decimals="3" rightDirectionSymbol=">" multilineAlign="0"/>
          <placement maxCurvedCharAngleOut="-25" maximumDistanceMapUnitScale="3x:0,0,0,0,0,0" placementFlags="10" overlapHandling="AllowOverlapIfRequired" prioritization="PreferCloser" overrunDistanceMapUnitScale="3x:0,0,0,0,0,0" fitInPolygonOnly="0" lineAnchorTextPoint="CenterOfText" geometryGenerator="" maximumDistanceUnit="MM" offsetUnits="MapUnit" repeatDistanceUnits="MapUnit" lineAnchorClipping="0" distMapUnitScale="3x:0,0,0,0,0,0" lineAnchorType="0" rotationUnit="AngleDegrees" maxCurvedCharAngleIn="25" overrunDistance="0" polygonPlacementFlags="2" xOffset="0" preserveRotation="0" offsetType="0" lineAnchorPercent="0.5" repeatDistance="0" geometryGeneratorType="PointGeometry" overrunDistanceUnit="MM" layerType="LineGeometry" centroidInside="0" dist="0" distUnits="MapUnit" centroidWhole="0" repeatDistanceMapUnitScale="3x:0,0,0,0,0,0" yOffset="0" placement="4" rotationAngle="0" priority="5" allowDegraded="1" predefinedPositionOrder="TR,TL,BR,BL,R,L,TSR,BSR" maximumDistance="0" labelOffsetMapUnitScale="3x:0,0,0,0,0,0" quadOffset="4" geometryGeneratorEnabled="0"/>
          <rendering scaleVisibility="0" fontMinPixelSize="3" labelPerPart="1" scaleMax="10000000" scaleMin="1" mergeLines="0" limitNumLabels="0" fontMaxPixelSize="10000" minFeatureSize="0" unplacedVisibility="0" maxNumLabels="2000" upsidedownLabels="2" obstacle="0" drawLabels="1" obstacleFactor="1" obstacleType="0" fontLimitPixelSize="0" zIndex="0"/>
          <dd_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties" type="Map">
                <Option name="BufferSize" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="0.45* &quot;Borda&quot;" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="Hali" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="'Center'" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="LabelRotation" type="Map">
                  <Option name="active" value="false" type="bool"/>
                  <Option name="type" value="1" type="int"/>
                  <Option name="val" value="" type="QString"/>
                </Option>
                <Option name="PositionX" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="x(line_interpolate_point($geometry,  length ($geometry)/2-500))&#xd;&#xa;&#xd;&#xa;+ (200 + 110*(length (&quot;nome_esq&quot;)/2 )) * (cos(&#xd;&#xa;&#xd;&#xa;atan2(  &#xd;&#xa;y( line_interpolate_point($geometry, length ($geometry)/2-499))  &#xd;&#xa;-y(line_interpolate_point($geometry, length ($geometry)/2-501)) ,&#xd;&#xa;x( line_interpolate_point($geometry, length ($geometry)/2-499))  &#xd;&#xa;-x(line_interpolate_point($geometry, length ($geometry)/2-501)) )&#xd;&#xa;+ pi()/2 &#xd;&#xa;))" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="PositionY" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="y(line_interpolate_point($geometry,  length ($geometry)/2-500))&#xd;&#xa;&#xd;&#xa;+ 300 * (sin(&#xd;&#xa;&#xd;&#xa;&#xd;&#xa;atan2(  &#xd;&#xa;y( line_interpolate_point($geometry, length ($geometry)/2-499))&#xd;&#xa;-y(line_interpolate_point($geometry, length ($geometry)/2-501)) ,&#xd;&#xa;x( line_interpolate_point($geometry, length ($geometry)/2-499)) &#xd;&#xa;-x(line_interpolate_point($geometry, length ($geometry)/2-501)) )&#xd;&#xa;+ pi()/2 &#xd;&#xa;)&#xd;&#xa;)" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="Size" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="&quot;tamanhoTexto&quot;" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="Vali" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="'Half'" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
              </Option>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </dd_properties>
          <callout type="simple">
            <Option type="Map">
              <Option name="anchorPoint" value="pole_of_inaccessibility" type="QString"/>
              <Option name="blendMode" value="0" type="int"/>
              <Option name="ddProperties" type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties"/>
                <Option name="type" value="collection" type="QString"/>
              </Option>
              <Option name="drawToAllParts" value="false" type="bool"/>
              <Option name="enabled" value="0" type="QString"/>
              <Option name="labelAnchorPoint" value="point_on_exterior" type="QString"/>
              <Option name="lineSymbol" value="&lt;symbol name=&quot;symbol&quot; alpha=&quot;1&quot; force_rhr=&quot;0&quot; is_animated=&quot;0&quot; clip_to_extent=&quot;1&quot; type=&quot;line&quot; frame_rate=&quot;10&quot;>&lt;data_defined_properties>&lt;Option type=&quot;Map&quot;>&lt;Option name=&quot;name&quot; value=&quot;&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;properties&quot;/>&lt;Option name=&quot;type&quot; value=&quot;collection&quot; type=&quot;QString&quot;/>&lt;/Option>&lt;/data_defined_properties>&lt;layer id=&quot;{6ce43fff-84ed-4856-a94f-0ea767a81f22}&quot; locked=&quot;0&quot; pass=&quot;0&quot; enabled=&quot;1&quot; class=&quot;SimpleLine&quot;>&lt;Option type=&quot;Map&quot;>&lt;Option name=&quot;align_dash_pattern&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;capstyle&quot; value=&quot;square&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;customdash&quot; value=&quot;5;2&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;customdash_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;customdash_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;dash_pattern_offset&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;dash_pattern_offset_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;dash_pattern_offset_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;draw_inside_polygon&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;joinstyle&quot; value=&quot;bevel&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;line_color&quot; value=&quot;60,60,60,255,rgb:0.23529411764705882,0.23529411764705882,0.23529411764705882,1&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;line_style&quot; value=&quot;solid&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;line_width&quot; value=&quot;0.3&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;line_width_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;offset&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;offset_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;offset_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;ring_filter&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_end&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_end_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_end_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_start&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_start_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_start_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;tweak_dash_pattern_on_corners&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;use_custom_dash&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;width_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;/Option>&lt;data_defined_properties>&lt;Option type=&quot;Map&quot;>&lt;Option name=&quot;name&quot; value=&quot;&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;properties&quot;/>&lt;Option name=&quot;type&quot; value=&quot;collection&quot; type=&quot;QString&quot;/>&lt;/Option>&lt;/data_defined_properties>&lt;/layer>&lt;/symbol>" type="QString"/>
              <Option name="minLength" value="0" type="double"/>
              <Option name="minLengthMapUnitScale" value="3x:0,0,0,0,0,0" type="QString"/>
              <Option name="minLengthUnit" value="MM" type="QString"/>
              <Option name="offsetFromAnchor" value="0" type="double"/>
              <Option name="offsetFromAnchorMapUnitScale" value="3x:0,0,0,0,0,0" type="QString"/>
              <Option name="offsetFromAnchorUnit" value="MM" type="QString"/>
              <Option name="offsetFromLabel" value="0" type="double"/>
              <Option name="offsetFromLabelMapUnitScale" value="3x:0,0,0,0,0,0" type="QString"/>
              <Option name="offsetFromLabelUnit" value="MM" type="QString"/>
            </Option>
          </callout>
        </settings>
      </rule>
      <rule description="Nome direita igual" key="{afa5902c-4e1e-4505-a4ae-ae0642e105e8}" filter=" &quot;tropa_esq&quot;  =  &quot;tropa_dir&quot; ">
        <settings calloutType="simple">
          <text-style previewBkgrdColor="255,255,255,255,rgb:1,1,1,1" tabStopDistanceMapUnitScale="3x:0,0,0,0,0,0" textColor="0,0,0,255,rgb:0,0,0,1" multilineHeightUnit="Percentage" fontSizeMapUnitScale="3x:0,0,0,0,0,0" forcedItalic="0" textOrientation="horizontal" blendMode="0" fontSizeUnit="MapUnit" fontLetterSpacing="0" stretchFactor="100" fieldName="nome_dir" fontSize="170" capitalization="0" isExpression="0" namedStyle="Normal" forcedBold="0" useSubstitutions="0" fontKerning="1" fontStrikeout="0" tabStopDistance="80" fontItalic="0" fontWeight="87" allowHtml="0" textOpacity="1" fontWordSpacing="0" legendString="Aa" fontFamily="Arial Black" fontUnderline="0" tabStopDistanceUnit="Point" multilineHeight="0">
            <families/>
            <text-buffer bufferOpacity="1" bufferSizeUnits="MapUnit" bufferColor="255,255,255,255,rgb:1,1,1,1" bufferDraw="1" bufferBlendMode="0" bufferSize="0.29999999999999999" bufferNoFill="0" bufferSizeMapUnitScale="3x:0,0,0,0,0,0" bufferJoinStyle="128"/>
            <text-mask maskSize2="1.5" maskEnabled="0" maskSizeUnits="MM" maskOpacity="1" maskJoinStyle="128" maskSize="1.5" maskedSymbolLayers="" maskType="0" maskSizeMapUnitScale="3x:0,0,0,0,0,0"/>
            <background shapeOffsetY="0" shapeRadiiMapUnitScale="3x:0,0,0,0,0,0" shapeJoinStyle="64" shapeOffsetUnit="MM" shapeOffsetMapUnitScale="3x:0,0,0,0,0,0" shapeRotationType="0" shapeBlendMode="0" shapeOpacity="1" shapeBorderWidthMapUnitScale="3x:0,0,0,0,0,0" shapeDraw="0" shapeSizeMapUnitScale="3x:0,0,0,0,0,0" shapeSizeType="0" shapeSizeY="0" shapeSVGFile="" shapeRadiiX="0" shapeBorderWidthUnit="MM" shapeRadiiUnit="MM" shapeType="0" shapeOffsetX="0" shapeFillColor="255,255,255,255,rgb:1,1,1,1" shapeSizeX="0" shapeRotation="0" shapeRadiiY="0" shapeBorderWidth="0" shapeBorderColor="128,128,128,255,rgb:0.50196078431372548,0.50196078431372548,0.50196078431372548,1" shapeSizeUnit="MM">
              <symbol name="markerSymbol" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="marker" frame_rate="10">
                <data_defined_properties>
                  <Option type="Map">
                    <Option name="name" value="" type="QString"/>
                    <Option name="properties"/>
                    <Option name="type" value="collection" type="QString"/>
                  </Option>
                </data_defined_properties>
                <layer id="" locked="0" pass="0" enabled="1" class="SimpleMarker">
                  <Option type="Map">
                    <Option name="angle" value="0" type="QString"/>
                    <Option name="cap_style" value="square" type="QString"/>
                    <Option name="color" value="183,72,75,255,rgb:0.71764705882352942,0.28235294117647058,0.29411764705882354,1" type="QString"/>
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
              <symbol name="fillSymbol" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="fill" frame_rate="10">
                <data_defined_properties>
                  <Option type="Map">
                    <Option name="name" value="" type="QString"/>
                    <Option name="properties"/>
                    <Option name="type" value="collection" type="QString"/>
                  </Option>
                </data_defined_properties>
                <layer id="" locked="0" pass="0" enabled="1" class="SimpleFill">
                  <Option type="Map">
                    <Option name="border_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                    <Option name="joinstyle" value="bevel" type="QString"/>
                    <Option name="offset" value="0,0" type="QString"/>
                    <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="offset_unit" value="MM" type="QString"/>
                    <Option name="outline_color" value="128,128,128,255,rgb:0.50196078431372548,0.50196078431372548,0.50196078431372548,1" type="QString"/>
                    <Option name="outline_style" value="no" type="QString"/>
                    <Option name="outline_width" value="0" type="QString"/>
                    <Option name="outline_width_unit" value="MM" type="QString"/>
                    <Option name="style" value="solid" type="QString"/>
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
            </background>
            <shadow shadowOffsetMapUnitScale="3x:0,0,0,0,0,0" shadowRadiusUnit="MM" shadowDraw="0" shadowUnder="0" shadowOffsetGlobal="1" shadowOffsetUnit="MM" shadowBlendMode="6" shadowScale="100" shadowRadius="1.5" shadowColor="0,0,0,255,rgb:0,0,0,1" shadowOffsetAngle="135" shadowRadiusAlphaOnly="0" shadowOpacity="0.69999999999999996" shadowOffsetDist="1" shadowRadiusMapUnitScale="3x:0,0,0,0,0,0"/>
            <dd_properties>
              <Option type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties"/>
                <Option name="type" value="collection" type="QString"/>
              </Option>
            </dd_properties>
            <substitutions/>
          </text-style>
          <text-format reverseDirectionSymbol="0" plussign="0" placeDirectionSymbol="0" wrapChar="|" formatNumbers="0" leftDirectionSymbol="&lt;" useMaxLineLengthForAutoWrap="1" addDirectionSymbol="0" autoWrapLength="0" decimals="3" rightDirectionSymbol=">" multilineAlign="0"/>
          <placement maxCurvedCharAngleOut="-25" maximumDistanceMapUnitScale="3x:0,0,0,0,0,0" placementFlags="12" overlapHandling="AllowOverlapIfRequired" prioritization="PreferCloser" overrunDistanceMapUnitScale="3x:0,0,0,0,0,0" fitInPolygonOnly="0" lineAnchorTextPoint="CenterOfText" geometryGenerator="" maximumDistanceUnit="MM" offsetUnits="MapUnit" repeatDistanceUnits="MM" lineAnchorClipping="0" distMapUnitScale="3x:0,0,0,0,0,0" lineAnchorType="0" rotationUnit="AngleDegrees" maxCurvedCharAngleIn="25" overrunDistance="0" polygonPlacementFlags="2" xOffset="0" preserveRotation="1" offsetType="0" lineAnchorPercent="0.5" repeatDistance="0" geometryGeneratorType="PointGeometry" overrunDistanceUnit="MM" layerType="LineGeometry" centroidInside="0" dist="0" distUnits="MM" centroidWhole="0" repeatDistanceMapUnitScale="3x:0,0,0,0,0,0" yOffset="0" placement="4" rotationAngle="0" priority="10" allowDegraded="1" predefinedPositionOrder="TR,TL,BR,BL,R,L,TSR,BSR" maximumDistance="0" labelOffsetMapUnitScale="3x:0,0,0,0,0,0" quadOffset="4" geometryGeneratorEnabled="0"/>
          <rendering scaleVisibility="0" fontMinPixelSize="3" labelPerPart="1" scaleMax="10000000" scaleMin="1" mergeLines="0" limitNumLabels="0" fontMaxPixelSize="10000" minFeatureSize="0" unplacedVisibility="0" maxNumLabels="2000" upsidedownLabels="2" obstacle="0" drawLabels="1" obstacleFactor="1" obstacleType="0" fontLimitPixelSize="0" zIndex="0"/>
          <dd_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties" type="Map">
                <Option name="BufferSize" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="0.45* &quot;Borda&quot;" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="BufferUnit" type="Map">
                  <Option name="active" value="false" type="bool"/>
                  <Option name="expression" value="0.45*&quot;Borda&quot;" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="Hali" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="'Center'" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="LabelRotation" type="Map">
                  <Option name="active" value="false" type="bool"/>
                  <Option name="type" value="1" type="int"/>
                  <Option name="val" value="" type="QString"/>
                </Option>
                <Option name="PositionX" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="x(line_interpolate_point($geometry,  length ($geometry)/2))&#xd;&#xa;&#xd;&#xa;+ (200 + 110*(length (&quot;nome_dir&quot;)/2 )) *cos(&#xd;&#xa;&#xd;&#xa;&#xd;&#xa;atan2(  &#xd;&#xa;y( line_interpolate_point($geometry, length ($geometry)/2+1)) &#xd;&#xa;-y(line_interpolate_point($geometry, length ($geometry)/2-1)),&#xd;&#xa;x( line_interpolate_point($geometry, length ($geometry)/2+1)) &#xd;&#xa;-x(line_interpolate_point($geometry, length ($geometry)/2-1)))&#xd;&#xa;- pi()/2 &#xd;&#xa;&#xd;&#xa;)" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="PositionY" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="y(line_interpolate_point($geometry,  length ($geometry)/2))&#xd;&#xa;&#xd;&#xa;+ 300 * (sin(&#xd;&#xa;&#xd;&#xa;&#xd;&#xa;atan2(  &#xd;&#xa;y( line_interpolate_point($geometry, length ($geometry)/2+1))&#xd;&#xa;-y(line_interpolate_point($geometry, length ($geometry)/2-1)) ,&#xd;&#xa;x( line_interpolate_point($geometry, length ($geometry)/2+1)) &#xd;&#xa;-x(line_interpolate_point($geometry, length ($geometry)/2-1)) )&#xd;&#xa;- pi()/2 &#xd;&#xa;)&#xd;&#xa;)" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="Size" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="&quot;tamanhoTexto&quot;" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="Vali" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="'Half'" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
              </Option>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </dd_properties>
          <callout type="simple">
            <Option type="Map">
              <Option name="anchorPoint" value="pole_of_inaccessibility" type="QString"/>
              <Option name="blendMode" value="0" type="int"/>
              <Option name="ddProperties" type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties"/>
                <Option name="type" value="collection" type="QString"/>
              </Option>
              <Option name="drawToAllParts" value="false" type="bool"/>
              <Option name="enabled" value="0" type="QString"/>
              <Option name="labelAnchorPoint" value="point_on_exterior" type="QString"/>
              <Option name="lineSymbol" value="&lt;symbol name=&quot;symbol&quot; alpha=&quot;1&quot; force_rhr=&quot;0&quot; is_animated=&quot;0&quot; clip_to_extent=&quot;1&quot; type=&quot;line&quot; frame_rate=&quot;10&quot;>&lt;data_defined_properties>&lt;Option type=&quot;Map&quot;>&lt;Option name=&quot;name&quot; value=&quot;&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;properties&quot;/>&lt;Option name=&quot;type&quot; value=&quot;collection&quot; type=&quot;QString&quot;/>&lt;/Option>&lt;/data_defined_properties>&lt;layer id=&quot;{87dd95d2-b7d8-4ee1-ac5b-a13ce3a4ab35}&quot; locked=&quot;0&quot; pass=&quot;0&quot; enabled=&quot;1&quot; class=&quot;SimpleLine&quot;>&lt;Option type=&quot;Map&quot;>&lt;Option name=&quot;align_dash_pattern&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;capstyle&quot; value=&quot;square&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;customdash&quot; value=&quot;5;2&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;customdash_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;customdash_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;dash_pattern_offset&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;dash_pattern_offset_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;dash_pattern_offset_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;draw_inside_polygon&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;joinstyle&quot; value=&quot;bevel&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;line_color&quot; value=&quot;60,60,60,255,rgb:0.23529411764705882,0.23529411764705882,0.23529411764705882,1&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;line_style&quot; value=&quot;solid&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;line_width&quot; value=&quot;0.3&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;line_width_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;offset&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;offset_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;offset_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;ring_filter&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_end&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_end_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_end_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_start&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_start_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_start_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;tweak_dash_pattern_on_corners&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;use_custom_dash&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;width_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;/Option>&lt;data_defined_properties>&lt;Option type=&quot;Map&quot;>&lt;Option name=&quot;name&quot; value=&quot;&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;properties&quot;/>&lt;Option name=&quot;type&quot; value=&quot;collection&quot; type=&quot;QString&quot;/>&lt;/Option>&lt;/data_defined_properties>&lt;/layer>&lt;/symbol>" type="QString"/>
              <Option name="minLength" value="0" type="double"/>
              <Option name="minLengthMapUnitScale" value="3x:0,0,0,0,0,0" type="QString"/>
              <Option name="minLengthUnit" value="MM" type="QString"/>
              <Option name="offsetFromAnchor" value="0" type="double"/>
              <Option name="offsetFromAnchorMapUnitScale" value="3x:0,0,0,0,0,0" type="QString"/>
              <Option name="offsetFromAnchorUnit" value="MM" type="QString"/>
              <Option name="offsetFromLabel" value="0" type="double"/>
              <Option name="offsetFromLabelMapUnitScale" value="3x:0,0,0,0,0,0" type="QString"/>
              <Option name="offsetFromLabelUnit" value="MM" type="QString"/>
            </Option>
          </callout>
        </settings>
      </rule>
      <rule description="Nome direita" key="{e9a0842e-4113-4ab7-8f20-ab0b12426761}" filter=" &quot;tropa_esq&quot;  &lt;>  &quot;tropa_dir&quot; ">
        <settings calloutType="simple">
          <text-style previewBkgrdColor="255,255,255,255,rgb:1,1,1,1" tabStopDistanceMapUnitScale="3x:0,0,0,0,0,0" textColor="0,0,0,255,rgb:0,0,0,1" multilineHeightUnit="Percentage" fontSizeMapUnitScale="3x:0,0,0,0,0,0" forcedItalic="0" textOrientation="horizontal" blendMode="0" fontSizeUnit="MapUnit" fontLetterSpacing="0" stretchFactor="100" fieldName="nome_dir" fontSize="170" capitalization="0" isExpression="0" namedStyle="Normal" forcedBold="0" useSubstitutions="0" fontKerning="1" fontStrikeout="0" tabStopDistance="80" fontItalic="0" fontWeight="87" allowHtml="0" textOpacity="1" fontWordSpacing="0" legendString="Aa" fontFamily="Arial Black" fontUnderline="0" tabStopDistanceUnit="Point" multilineHeight="0">
            <families/>
            <text-buffer bufferOpacity="1" bufferSizeUnits="MapUnit" bufferColor="255,255,255,255,rgb:1,1,1,1" bufferDraw="1" bufferBlendMode="0" bufferSize="0.0001" bufferNoFill="0" bufferSizeMapUnitScale="3x:0,0,0,0,0,0" bufferJoinStyle="128"/>
            <text-mask maskSize2="1.5" maskEnabled="0" maskSizeUnits="MM" maskOpacity="1" maskJoinStyle="128" maskSize="1.5" maskedSymbolLayers="" maskType="0" maskSizeMapUnitScale="3x:0,0,0,0,0,0"/>
            <background shapeOffsetY="0" shapeRadiiMapUnitScale="3x:0,0,0,0,0,0" shapeJoinStyle="64" shapeOffsetUnit="MM" shapeOffsetMapUnitScale="3x:0,0,0,0,0,0" shapeRotationType="0" shapeBlendMode="0" shapeOpacity="1" shapeBorderWidthMapUnitScale="3x:0,0,0,0,0,0" shapeDraw="0" shapeSizeMapUnitScale="3x:0,0,0,0,0,0" shapeSizeType="0" shapeSizeY="0" shapeSVGFile="" shapeRadiiX="0" shapeBorderWidthUnit="MM" shapeRadiiUnit="MM" shapeType="0" shapeOffsetX="0" shapeFillColor="255,255,255,255,rgb:1,1,1,1" shapeSizeX="0" shapeRotation="0" shapeRadiiY="0" shapeBorderWidth="0" shapeBorderColor="128,128,128,255,rgb:0.50196078431372548,0.50196078431372548,0.50196078431372548,1" shapeSizeUnit="MM">
              <symbol name="markerSymbol" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="marker" frame_rate="10">
                <data_defined_properties>
                  <Option type="Map">
                    <Option name="name" value="" type="QString"/>
                    <Option name="properties"/>
                    <Option name="type" value="collection" type="QString"/>
                  </Option>
                </data_defined_properties>
                <layer id="" locked="0" pass="0" enabled="1" class="SimpleMarker">
                  <Option type="Map">
                    <Option name="angle" value="0" type="QString"/>
                    <Option name="cap_style" value="square" type="QString"/>
                    <Option name="color" value="152,125,183,255,rgb:0.59607843137254901,0.49019607843137253,0.71764705882352942,1" type="QString"/>
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
              <symbol name="fillSymbol" alpha="1" force_rhr="0" is_animated="0" clip_to_extent="1" type="fill" frame_rate="10">
                <data_defined_properties>
                  <Option type="Map">
                    <Option name="name" value="" type="QString"/>
                    <Option name="properties"/>
                    <Option name="type" value="collection" type="QString"/>
                  </Option>
                </data_defined_properties>
                <layer id="" locked="0" pass="0" enabled="1" class="SimpleFill">
                  <Option type="Map">
                    <Option name="border_width_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="color" value="255,255,255,255,rgb:1,1,1,1" type="QString"/>
                    <Option name="joinstyle" value="bevel" type="QString"/>
                    <Option name="offset" value="0,0" type="QString"/>
                    <Option name="offset_map_unit_scale" value="3x:0,0,0,0,0,0" type="QString"/>
                    <Option name="offset_unit" value="MM" type="QString"/>
                    <Option name="outline_color" value="128,128,128,255,rgb:0.50196078431372548,0.50196078431372548,0.50196078431372548,1" type="QString"/>
                    <Option name="outline_style" value="no" type="QString"/>
                    <Option name="outline_width" value="0" type="QString"/>
                    <Option name="outline_width_unit" value="MM" type="QString"/>
                    <Option name="style" value="solid" type="QString"/>
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
            </background>
            <shadow shadowOffsetMapUnitScale="3x:0,0,0,0,0,0" shadowRadiusUnit="MM" shadowDraw="0" shadowUnder="0" shadowOffsetGlobal="1" shadowOffsetUnit="MM" shadowBlendMode="6" shadowScale="100" shadowRadius="1.5" shadowColor="0,0,0,255,rgb:0,0,0,1" shadowOffsetAngle="135" shadowRadiusAlphaOnly="0" shadowOpacity="0.69999999999999996" shadowOffsetDist="1" shadowRadiusMapUnitScale="3x:0,0,0,0,0,0"/>
            <dd_properties>
              <Option type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties"/>
                <Option name="type" value="collection" type="QString"/>
              </Option>
            </dd_properties>
            <substitutions/>
          </text-style>
          <text-format reverseDirectionSymbol="0" plussign="0" placeDirectionSymbol="0" wrapChar="|" formatNumbers="0" leftDirectionSymbol="&lt;" useMaxLineLengthForAutoWrap="1" addDirectionSymbol="0" autoWrapLength="0" decimals="3" rightDirectionSymbol=">" multilineAlign="0"/>
          <placement maxCurvedCharAngleOut="-25" maximumDistanceMapUnitScale="3x:0,0,0,0,0,0" placementFlags="13" overlapHandling="AllowOverlapIfRequired" prioritization="PreferCloser" overrunDistanceMapUnitScale="3x:0,0,0,0,0,0" fitInPolygonOnly="0" lineAnchorTextPoint="CenterOfText" geometryGenerator="" maximumDistanceUnit="MM" offsetUnits="MapUnit" repeatDistanceUnits="MapUnit" lineAnchorClipping="0" distMapUnitScale="3x:0,0,0,0,0,0" lineAnchorType="0" rotationUnit="AngleDegrees" maxCurvedCharAngleIn="24" overrunDistance="0" polygonPlacementFlags="2" xOffset="0" preserveRotation="1" offsetType="0" lineAnchorPercent="0.5" repeatDistance="0" geometryGeneratorType="PointGeometry" overrunDistanceUnit="MM" layerType="LineGeometry" centroidInside="0" dist="0.001" distUnits="MapUnit" centroidWhole="0" repeatDistanceMapUnitScale="3x:0,0,0,0,0,0" yOffset="0" placement="4" rotationAngle="0" priority="5" allowDegraded="1" predefinedPositionOrder="TR,TL,BR,BL,R,L,TSR,BSR" maximumDistance="0" labelOffsetMapUnitScale="3x:0,0,0,0,0,0" quadOffset="4" geometryGeneratorEnabled="0"/>
          <rendering scaleVisibility="0" fontMinPixelSize="3" labelPerPart="0" scaleMax="10000000" scaleMin="1" mergeLines="0" limitNumLabels="0" fontMaxPixelSize="10000" minFeatureSize="0" unplacedVisibility="0" maxNumLabels="2000" upsidedownLabels="1" obstacle="0" drawLabels="1" obstacleFactor="1" obstacleType="0" fontLimitPixelSize="0" zIndex="0"/>
          <dd_properties>
            <Option type="Map">
              <Option name="name" value="" type="QString"/>
              <Option name="properties" type="Map">
                <Option name="BufferSize" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="0.45* &quot;Borda&quot;" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="Hali" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="'Center'" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="LabelRotation" type="Map">
                  <Option name="active" value="false" type="bool"/>
                  <Option name="type" value="1" type="int"/>
                  <Option name="val" value="" type="QString"/>
                </Option>
                <Option name="PositionX" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="x(line_interpolate_point($geometry,  length ($geometry)/2+500))&#xd;&#xa;&#xd;&#xa;+ (200 + 110 * (length (&quot;nome_dir&quot;)/2 )) * (cos(&#xd;&#xa;&#xd;&#xa;atan2(  &#xd;&#xa;y( line_interpolate_point($geometry, length ($geometry)/2+501))  &#xd;&#xa;-y(line_interpolate_point($geometry, length ($geometry)/2+499)) ,&#xd;&#xa;x( line_interpolate_point($geometry, length ($geometry)/2+501))  &#xd;&#xa;-x(line_interpolate_point($geometry, length ($geometry)/2+499)) )&#xd;&#xa;- pi()/2 &#xd;&#xa;))" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="PositionY" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="y(line_interpolate_point($geometry,  length ($geometry)/2+500))&#xd;&#xa;&#xd;&#xa;+ 300 * (sin(&#xd;&#xa;&#xd;&#xa;&#xd;&#xa;atan2(  &#xd;&#xa;y( line_interpolate_point($geometry, length ($geometry)/2+501))&#xd;&#xa;-y(line_interpolate_point($geometry, length ($geometry)/2+499)) ,&#xd;&#xa;x( line_interpolate_point($geometry, length ($geometry)/2+501)) &#xd;&#xa;-x(line_interpolate_point($geometry, length ($geometry)/2+499)) )&#xd;&#xa;- pi()/2 &#xd;&#xa;)&#xd;&#xa;)" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="Size" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="&quot;tamanhoTexto&quot;" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
                <Option name="Vali" type="Map">
                  <Option name="active" value="true" type="bool"/>
                  <Option name="expression" value="'Half'" type="QString"/>
                  <Option name="type" value="3" type="int"/>
                </Option>
              </Option>
              <Option name="type" value="collection" type="QString"/>
            </Option>
          </dd_properties>
          <callout type="simple">
            <Option type="Map">
              <Option name="anchorPoint" value="pole_of_inaccessibility" type="QString"/>
              <Option name="blendMode" value="0" type="int"/>
              <Option name="ddProperties" type="Map">
                <Option name="name" value="" type="QString"/>
                <Option name="properties"/>
                <Option name="type" value="collection" type="QString"/>
              </Option>
              <Option name="drawToAllParts" value="false" type="bool"/>
              <Option name="enabled" value="0" type="QString"/>
              <Option name="labelAnchorPoint" value="point_on_exterior" type="QString"/>
              <Option name="lineSymbol" value="&lt;symbol name=&quot;symbol&quot; alpha=&quot;1&quot; force_rhr=&quot;0&quot; is_animated=&quot;0&quot; clip_to_extent=&quot;1&quot; type=&quot;line&quot; frame_rate=&quot;10&quot;>&lt;data_defined_properties>&lt;Option type=&quot;Map&quot;>&lt;Option name=&quot;name&quot; value=&quot;&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;properties&quot;/>&lt;Option name=&quot;type&quot; value=&quot;collection&quot; type=&quot;QString&quot;/>&lt;/Option>&lt;/data_defined_properties>&lt;layer id=&quot;{47f893c4-0912-48f2-b520-9fb32dabb387}&quot; locked=&quot;0&quot; pass=&quot;0&quot; enabled=&quot;1&quot; class=&quot;SimpleLine&quot;>&lt;Option type=&quot;Map&quot;>&lt;Option name=&quot;align_dash_pattern&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;capstyle&quot; value=&quot;square&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;customdash&quot; value=&quot;5;2&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;customdash_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;customdash_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;dash_pattern_offset&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;dash_pattern_offset_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;dash_pattern_offset_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;draw_inside_polygon&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;joinstyle&quot; value=&quot;bevel&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;line_color&quot; value=&quot;60,60,60,255,rgb:0.23529411764705882,0.23529411764705882,0.23529411764705882,1&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;line_style&quot; value=&quot;solid&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;line_width&quot; value=&quot;0.3&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;line_width_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;offset&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;offset_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;offset_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;ring_filter&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_end&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_end_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_end_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_start&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_start_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;trim_distance_start_unit&quot; value=&quot;MM&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;tweak_dash_pattern_on_corners&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;use_custom_dash&quot; value=&quot;0&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;width_map_unit_scale&quot; value=&quot;3x:0,0,0,0,0,0&quot; type=&quot;QString&quot;/>&lt;/Option>&lt;data_defined_properties>&lt;Option type=&quot;Map&quot;>&lt;Option name=&quot;name&quot; value=&quot;&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;properties&quot;/>&lt;Option name=&quot;type&quot; value=&quot;collection&quot; type=&quot;QString&quot;/>&lt;/Option>&lt;/data_defined_properties>&lt;/layer>&lt;/symbol>" type="QString"/>
              <Option name="minLength" value="0" type="double"/>
              <Option name="minLengthMapUnitScale" value="3x:0,0,0,0,0,0" type="QString"/>
              <Option name="minLengthUnit" value="MM" type="QString"/>
              <Option name="offsetFromAnchor" value="0" type="double"/>
              <Option name="offsetFromAnchorMapUnitScale" value="3x:0,0,0,0,0,0" type="QString"/>
              <Option name="offsetFromAnchorUnit" value="MM" type="QString"/>
              <Option name="offsetFromLabel" value="0" type="double"/>
              <Option name="offsetFromLabelMapUnitScale" value="3x:0,0,0,0,0,0" type="QString"/>
              <Option name="offsetFromLabelUnit" value="MM" type="QString"/>
            </Option>
          </callout>
        </settings>
      </rule>
    </rules>
  </labeling>
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
    <field name="tropa_esq" configurationFlags="NoFlag">
      <editWidget type="ValueMap">
        <config>
          <Option type="Map">
            <Option name="map" type="List">
              <Option type="Map">
                <Option name="Batalhão ou grupo de artilharia" value="4" type="QString"/>
              </Option>
              <Option type="Map">
                <Option name="Brigada" value="3" type="QString"/>
              </Option>
              <Option type="Map">
                <Option name="Companhia, Esquadrão ou Bateria" value="5" type="QString"/>
              </Option>
              <Option type="Map">
                <Option name="Corpo de Exército" value="1" type="QString"/>
              </Option>
              <Option type="Map">
                <Option name="Divisão de Exército" value="2" type="QString"/>
              </Option>
              <Option type="Map">
                <Option name="Pelotão, Bia de tiro (Art) ou Seç Art" value="6" type="QString"/>
              </Option>
              <Option type="Map">
                <Option name="Regimento de cavalaria" value="7" type="QString"/>
              </Option>
            </Option>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="tropa_dir" configurationFlags="NoFlag">
      <editWidget type="ValueMap">
        <config>
          <Option type="Map">
            <Option name="map" type="List">
              <Option type="Map">
                <Option name="Batalhão ou grupo de artilharia" value="4" type="QString"/>
              </Option>
              <Option type="Map">
                <Option name="Brigada" value="3" type="QString"/>
              </Option>
              <Option type="Map">
                <Option name="Companhia, Esquadrão ou Bateria" value="5" type="QString"/>
              </Option>
              <Option type="Map">
                <Option name="Corpo de Exército" value="1" type="QString"/>
              </Option>
              <Option type="Map">
                <Option name="Divisão de Exército" value="2" type="QString"/>
              </Option>
              <Option type="Map">
                <Option name="Pelotão, Bia de tiro (Art) ou Seç Art" value="6" type="QString"/>
              </Option>
              <Option type="Map">
                <Option name="Regimento de cavalaria" value="7" type="QString"/>
              </Option>
            </Option>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="nome_esq" configurationFlags="NoFlag">
      <editWidget type="TextEdit">
        <config>
          <Option type="Map">
            <Option name="IsMultiline" value="false" type="bool"/>
            <Option name="UseHtml" value="false" type="bool"/>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="nome_dir" configurationFlags="NoFlag">
      <editWidget type="TextEdit">
        <config>
          <Option type="Map">
            <Option name="IsMultiline" value="false" type="bool"/>
            <Option name="UseHtml" value="false" type="bool"/>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="Borda" configurationFlags="NoFlag">
      <editWidget type="ValueMap">
        <config>
          <Option type="Map">
            <Option name="map" type="List">
              <Option type="Map">
                <Option name="Borda Espessa" value="55" type="QString"/>
              </Option>
              <Option type="Map">
                <Option name="Borda Fina" value="35" type="QString"/>
              </Option>
              <Option type="Map">
                <Option name="Sem Borda" value="0" type="QString"/>
              </Option>
            </Option>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="tamanhoTexto" configurationFlags="NoFlag">
      <editWidget type="TextEdit">
        <config>
          <Option type="Map">
            <Option name="IsMultiline" value="false" type="bool"/>
            <Option name="UseHtml" value="false" type="bool"/>
          </Option>
        </config>
      </editWidget>
    </field>
  </fieldConfiguration>
  <aliases>
    <alias name="" field="fid" index="0"/>
    <alias name="Tropa Esquerda" field="tropa_esq" index="1"/>
    <alias name="Tropa Direita" field="tropa_dir" index="2"/>
    <alias name="Designação Esquerda" field="nome_esq" index="3"/>
    <alias name="Designação Direita" field="nome_dir" index="4"/>
    <alias name="Borda" field="Borda" index="5"/>
    <alias name="Tamanho do Texto" field="tamanhoTexto" index="6"/>
  </aliases>
  <splitPolicies>
    <policy policy="Duplicate" field="fid"/>
    <policy policy="Duplicate" field="tropa_esq"/>
    <policy policy="Duplicate" field="tropa_dir"/>
    <policy policy="Duplicate" field="nome_esq"/>
    <policy policy="Duplicate" field="nome_dir"/>
    <policy policy="Duplicate" field="Borda"/>
    <policy policy="Duplicate" field="tamanhoTexto"/>
  </splitPolicies>
  <duplicatePolicies>
    <policy policy="Duplicate" field="fid"/>
    <policy policy="Duplicate" field="tropa_esq"/>
    <policy policy="Duplicate" field="tropa_dir"/>
    <policy policy="Duplicate" field="nome_esq"/>
    <policy policy="Duplicate" field="nome_dir"/>
    <policy policy="Duplicate" field="Borda"/>
    <policy policy="Duplicate" field="tamanhoTexto"/>
  </duplicatePolicies>
  <defaults>
    <default expression="" applyOnUpdate="0" field="fid"/>
    <default expression="" applyOnUpdate="0" field="tropa_esq"/>
    <default expression="" applyOnUpdate="0" field="tropa_dir"/>
    <default expression="" applyOnUpdate="0" field="nome_esq"/>
    <default expression="" applyOnUpdate="0" field="nome_dir"/>
    <default expression="0" applyOnUpdate="0" field="Borda"/>
    <default expression="170" applyOnUpdate="0" field="tamanhoTexto"/>
  </defaults>
  <constraints>
    <constraint exp_strength="0" constraints="3" unique_strength="1" notnull_strength="1" field="fid"/>
    <constraint exp_strength="0" constraints="0" unique_strength="0" notnull_strength="0" field="tropa_esq"/>
    <constraint exp_strength="0" constraints="0" unique_strength="0" notnull_strength="0" field="tropa_dir"/>
    <constraint exp_strength="0" constraints="0" unique_strength="0" notnull_strength="0" field="nome_esq"/>
    <constraint exp_strength="0" constraints="0" unique_strength="0" notnull_strength="0" field="nome_dir"/>
    <constraint exp_strength="0" constraints="0" unique_strength="0" notnull_strength="0" field="Borda"/>
    <constraint exp_strength="0" constraints="0" unique_strength="0" notnull_strength="0" field="tamanhoTexto"/>
  </constraints>
  <constraintExpressions>
    <constraint desc="" exp="" field="fid"/>
    <constraint desc="" exp="" field="tropa_esq"/>
    <constraint desc="" exp="" field="tropa_dir"/>
    <constraint desc="" exp="" field="nome_esq"/>
    <constraint desc="" exp="" field="nome_dir"/>
    <constraint desc="" exp="" field="Borda"/>
    <constraint desc="" exp="" field="tamanhoTexto"/>
  </constraintExpressions>
  <expressionfields/>
  <editform tolerant="1">OSGEO4~1/bin</editform>
  <editforminit/>
  <editforminitcodesource>0</editforminitcodesource>
  <editforminitfilepath>OSGEO4~1/bin</editforminitfilepath>
  <editforminitcode><![CDATA[# -*- codificação: utf-8 -*-"""Os formulários do QGIS podem ter uma função Python que é chamada quandoo formulário é aberto.QGIS forms can have a Python function that is called when the form isopened.Use esta função para adicionar lógica extra aos seus formulários.Entre com o nome da função no campo "Python Init function".Un exemplo a seguir:"""a partir de PyQt4.QtGui importe QWidgetdef my_form_open(diálogo, camada, feição):	geom = feature.geometry()	control = dialog.findChild(QWidget, "MyLineEdit")]]></editforminitcode>
  <featformsuppress>0</featformsuppress>
  <editorlayout>tablayout</editorlayout>
  <attributeEditorForm>
    <labelStyle overrideLabelColor="0" labelColor="" overrideLabelFont="0">
      <labelFont description="MS Shell Dlg 2,8.3,-1,5,50,0,0,0,0,0" italic="0" style="" bold="0" strikethrough="0" underline="0"/>
    </labelStyle>
    <attributeEditorField name="tropa_esq" showLabel="1" verticalStretch="0" horizontalStretch="0" index="1">
      <labelStyle overrideLabelColor="0" labelColor="" overrideLabelFont="0">
        <labelFont description="MS Shell Dlg 2,8.3,-1,5,50,0,0,0,0,0" italic="0" style="" bold="0" strikethrough="0" underline="0"/>
      </labelStyle>
    </attributeEditorField>
    <attributeEditorField name="tropa_dir" showLabel="1" verticalStretch="0" horizontalStretch="0" index="2">
      <labelStyle overrideLabelColor="0" labelColor="" overrideLabelFont="0">
        <labelFont description="MS Shell Dlg 2,8.3,-1,5,50,0,0,0,0,0" italic="0" style="" bold="0" strikethrough="0" underline="0"/>
      </labelStyle>
    </attributeEditorField>
    <attributeEditorField name="nome_esq" showLabel="1" verticalStretch="0" horizontalStretch="0" index="3">
      <labelStyle overrideLabelColor="0" labelColor="" overrideLabelFont="0">
        <labelFont description="MS Shell Dlg 2,8.3,-1,5,50,0,0,0,0,0" italic="0" style="" bold="0" strikethrough="0" underline="0"/>
      </labelStyle>
    </attributeEditorField>
    <attributeEditorField name="nome_dir" showLabel="1" verticalStretch="0" horizontalStretch="0" index="4">
      <labelStyle overrideLabelColor="0" labelColor="" overrideLabelFont="0">
        <labelFont description="MS Shell Dlg 2,8.3,-1,5,50,0,0,0,0,0" italic="0" style="" bold="0" strikethrough="0" underline="0"/>
      </labelStyle>
    </attributeEditorField>
    <attributeEditorField name="tamanhoTexto" showLabel="1" verticalStretch="0" horizontalStretch="0" index="6">
      <labelStyle overrideLabelColor="0" labelColor="" overrideLabelFont="0">
        <labelFont description="MS Shell Dlg 2,8.3,-1,5,50,0,0,0,0,0" italic="0" style="" bold="0" strikethrough="0" underline="0"/>
      </labelStyle>
    </attributeEditorField>
    <attributeEditorField name="Borda" showLabel="1" verticalStretch="0" horizontalStretch="0" index="5">
      <labelStyle overrideLabelColor="0" labelColor="" overrideLabelFont="0">
        <labelFont description="MS Shell Dlg 2,8.3,-1,5,50,0,0,0,0,0" italic="0" style="" bold="0" strikethrough="0" underline="0"/>
      </labelStyle>
    </attributeEditorField>
  </attributeEditorForm>
  <editable>
    <field name="Borda" editable="1"/>
    <field name="Cor" editable="1"/>
    <field name="fid" editable="1"/>
    <field name="nome_dir" editable="1"/>
    <field name="nome_esq" editable="1"/>
    <field name="pkuid" editable="1"/>
    <field name="rot_centro_dir" editable="1"/>
    <field name="rot_centro_esq" editable="1"/>
    <field name="rot_dir" editable="1"/>
    <field name="rot_esq" editable="1"/>
    <field name="rot_simb_centro" editable="0"/>
    <field name="rot_simb_dir" editable="0"/>
    <field name="rot_simb_esq" editable="0"/>
    <field name="tamanhoTexto" editable="1"/>
    <field name="tropa_dir" editable="1"/>
    <field name="tropa_esq" editable="1"/>
    <field name="x_centro_dir" editable="1"/>
    <field name="x_centro_esq" editable="1"/>
    <field name="x_dir" editable="1"/>
    <field name="x_esq" editable="1"/>
    <field name="y_centro_dir" editable="1"/>
    <field name="y_centro_esq" editable="1"/>
    <field name="y_dir" editable="1"/>
    <field name="y_esq" editable="1"/>
  </editable>
  <labelOnTop>
    <field name="Borda" labelOnTop="0"/>
    <field name="Cor" labelOnTop="0"/>
    <field name="fid" labelOnTop="0"/>
    <field name="nome_dir" labelOnTop="0"/>
    <field name="nome_esq" labelOnTop="0"/>
    <field name="pkuid" labelOnTop="0"/>
    <field name="rot_centro_dir" labelOnTop="0"/>
    <field name="rot_centro_esq" labelOnTop="0"/>
    <field name="rot_dir" labelOnTop="0"/>
    <field name="rot_esq" labelOnTop="0"/>
    <field name="rot_simb_centro" labelOnTop="0"/>
    <field name="rot_simb_dir" labelOnTop="0"/>
    <field name="rot_simb_esq" labelOnTop="0"/>
    <field name="tamanhoTexto" labelOnTop="0"/>
    <field name="tropa_dir" labelOnTop="0"/>
    <field name="tropa_esq" labelOnTop="0"/>
    <field name="x_centro_dir" labelOnTop="0"/>
    <field name="x_centro_esq" labelOnTop="0"/>
    <field name="x_dir" labelOnTop="0"/>
    <field name="x_esq" labelOnTop="0"/>
    <field name="y_centro_dir" labelOnTop="0"/>
    <field name="y_centro_esq" labelOnTop="0"/>
    <field name="y_dir" labelOnTop="0"/>
    <field name="y_esq" labelOnTop="0"/>
  </labelOnTop>
  <reuseLastValue>
    <field name="Borda" reuseLastValue="0"/>
    <field name="fid" reuseLastValue="0"/>
    <field name="nome_dir" reuseLastValue="0"/>
    <field name="nome_esq" reuseLastValue="0"/>
    <field name="tamanhoTexto" reuseLastValue="0"/>
    <field name="tropa_dir" reuseLastValue="0"/>
    <field name="tropa_esq" reuseLastValue="0"/>
  </reuseLastValue>
  <dataDefinedFieldProperties/>
  <widgets/>
  <layerGeometryType>1</layerGeometryType>
</qgis>
