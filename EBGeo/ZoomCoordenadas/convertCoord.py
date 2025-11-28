from qgis.PyQt import QtWidgets
from . import utmLatLon, mgrs

def conversao(self):
    origem = self.origemCombo.currentText()
    destino = self.destinoCombo.currentText()
    a = self.inputCoord.text().strip()

    if origem == "Lat/Lon Decimal":
        try:
            latlon = [s.strip() for s in a.split(',')]
            if len(latlon) != 2:
                raise ValueError("Formato inválido")
            lat = float(latlon[0])
            lon = float(latlon[1])
        except Exception:
            QtWidgets.QMessageBox.warning(self, "Erro", "Coordenada Lat/Lon inválida.")
            return
        if destino == "Lat/Lon GMS":
            str_dms = utmLatLon.decimal_to_dms(lat, lon)
            self.outputCoord.setText(str_dms)
        if destino == "UTM":
            zone_num, zone_letter, easting, northing = utmLatLon.latLon2UtmParameters(lat, lon)
            str_utm = f"{zone_num}{zone_letter} {int(easting)} {int(northing)}"
            self.outputCoord.setText(str_utm)
        if destino == "MGRS":
            str_mgrs = mgrs.toMgrs(lat, lon, 5)
            self.outputCoord.setText(str_mgrs)


    if origem == "Lat/Lon GMS":
        try:
            latlon = [s.strip() for s in a.split(',')]
            if len(latlon) != 2:
                raise ValueError("Formato inválido")
            lat_dms = utmLatLon.dms_to_decimal(latlon[0])
            lon_dms = utmLatLon.dms_to_decimal(latlon[1])
        except Exception:
            QtWidgets.QMessageBox.warning(self, "Erro", "Coordenada Lat/Lon GMS inválida.")
            return
        if destino == "Lat/Lon Decimal":
            str_decimal = f"{lat_dms:.6f}, {lon_dms:.6f}"
            self.outputCoord.setText(str_decimal)
        if destino == "UTM":
            zone_num, zone_letter, easting, northing = utmLatLon.latLon2UtmParameters(lat_dms, lon_dms)
            str_utm = f"{zone_num}{zone_letter} {int(easting)} {int(northing)}"
            self.outputCoord.setText(str_utm)
        if destino == "MGRS":
            str_mgrs = mgrs.toMgrs(lat_dms, lon_dms, 5)
            self.outputCoord.setText(str_mgrs)


    if origem == "UTM":  
        if utmLatLon.isUtm(a):
            latlon = utmLatLon.utm2LatLon(a)
            lat = float(latlon[0])
            lon = float(latlon[1]) 
        else:
            QtWidgets.QMessageBox.warning(self, "Erro", "Coordenada UTM inválida.")
            return
        if destino == "Lat/Lon Decimal":
            str_decimal = f"{lat:.6f}, {lon:.6f}"
            self.outputCoord.setText(str_decimal)
        if destino == "Lat/Lon GMS":
            str_dms = utmLatLon.decimal_to_dms(lat, lon)
            self.outputCoord.setText(str_dms)
        if destino == "MGRS":
            str_mgrs = mgrs.toMgrs(lat, lon, 5)
            self.outputCoord.setText(str_mgrs)


    if origem == "MGRS":
        try:
            lat, lon = mgrs.toWgs(a)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Erro", f"{e}")
            return
        if destino == "Lat/Lon Decimal":
            str_decimal = f"{lat:.6f}, {lon:.6f}"
            self.outputCoord.setText(str_decimal)
        if destino == "Lat/Lon GMS":
            str_dms = utmLatLon.decimal_to_dms(lat, lon)
            self.outputCoord.setText(str_dms)
        if destino == "UTM":
            zone_num, zone_letter, easting, northing = utmLatLon.latLon2UtmParameters(lat, lon)
            str_utm = f"{zone_num}{zone_letter} {int(easting)} {int(northing)}"
            self.outputCoord.setText(str_utm)