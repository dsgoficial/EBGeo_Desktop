from qgis.core import QgsPointXY, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject
import re

class UtmException(Exception):
    pass

def utmParse(utm_str):
    import re
    utm = utm_str.strip().upper()
    m = re.match(r'(\d+)\s*([NS])\s+(\d+\.?\d*)\s+(\d+\.?\d*)', utm)
    if m:
        zone = int(m.group(1))
        hemisphere = m.group(2)
        easting = float(m.group(3))
        northing = float(m.group(4))
        return zone, hemisphere, easting, northing
    raise UtmException("Invalid UTM coordinate")

def utm2Point(utm_str, crs="EPSG:4326"):
    zone, hemisphere, easting, northing = utmParse(utm_str)
    utmcrs = QgsCoordinateReferenceSystem(utmGetEpsg(hemisphere, zone))
    pt = QgsPointXY(easting, northing)
    utmtrans = QgsCoordinateTransform(utmcrs, QgsCoordinateReferenceSystem(crs), QgsProject.instance())
    return utmtrans.transform(pt)

def isUtm(utm_str):
    try:
        utmParse(utm_str)
        return True
    except Exception:
        return False
    
def latLon2UtmZone(lat, lon):
    if lon < -180 or lon > 360:
        raise UtmException(tr('Invalid longitude'))
    if lat > 84.5 or lat < -80.5:
        raise UtmException(tr('Invalid latitude'))
    if lon < 180:
        zone = int(31 + (lon / 6.0))
    else:
        zone = int((lon / 6) - 29)

    if zone > 60:
        zone = 1
    # Handle UTM special cases
    if 56.0 <= lat < 64.0 and 3.0 <= lon < 12.0:
        zone = 32

    if 72.0 <= lat < 84.0:
        if 0.0 <= lon < 9.0:
            zone = 31
        elif 9.0 <= lon < 21.0:
            zone = 33
        elif 21.0 <= lon < 33.0:
            zone = 35
        elif 33.0 <= lon < 42.0:
            zone = 37

    if lat < 0:
        hemisphere = 'S'
    else:
        hemisphere = 'N'
    return(zone, hemisphere)

def latLon2UtmParameters(lat, lon):
    zone, hemisphere = latLon2UtmZone(lat, lon)
    epsg = utmGetEpsg(hemisphere, zone)
    utmcrs = QgsCoordinateReferenceSystem(epsg)
    epsg4326 = QgsCoordinateReferenceSystem('EPSG:4326')
    utmtrans = QgsCoordinateTransform(epsg4326, utmcrs, QgsProject.instance())
    pt = QgsPointXY(lon, lat)
    utmpt = utmtrans.transform(pt)
    return(zone, hemisphere, utmpt.x(), utmpt.y())

def utmGetEpsg(hemisphere, zone):
    if hemisphere == "N":
        code = 32600 + zone
    else:
        code = 32700 + zone
    return f"EPSG:{code}"


# Função DMS multilingue
def dms_to_decimal(dms_str):
    """
    Converte DMS para decimal.
    Aceita abreviações PT (N/S/L/O) e EN (N/S/E/W)
    """
    pattern = r"(\d+)[°\s]+(\d+)[\'\s]+(\d+(?:\.\d+)?)[\"\'\s]*([NSEWLO])?"
    match = re.match(pattern, dms_str.strip(), re.IGNORECASE)
    if not match:
        raise ValueError(f"Formato DMS inválido: {dms_str}")

    deg, minutes, seconds, hemi = match.groups()
    decimal = float(deg) + float(minutes)/60 + float(seconds)/3600

    if hemi:
        hemi = hemi.upper()
        if hemi in ['S', 'O', 'W']:  # Sul/Oeste em PT ou W em EN
            decimal *= -1
    return decimal

def decimal_to_dms(lat, lon):
    """Converte decimal para graus/min/seg"""
    def dms(value, is_lat=True):
        degrees = int(abs(value))
        minutes = int((abs(value) - degrees) * 60)
        seconds = (abs(value) - degrees - minutes/60) * 3600
        hemi = 'N' if (value >= 0 and is_lat) else 'S' if is_lat else 'L' if value >= 0 else 'O'
        str = f"{degrees}°{minutes}'{seconds:.2f}\"{hemi}"
        return str
    return f"{dms(lat, True)}  {dms(lon, False)}"