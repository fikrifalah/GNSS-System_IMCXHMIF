from pydantic import BaseModel, Field
from typing import List, Optional

# --- Configuration & Admin schemas ---
class StationCreate(BaseModel):
    id: str = Field(..., example="rover-01")
    name: str = Field(..., example="Rover-01")
    type: str = Field(..., example="rover") # "base" or "rover"
    reference_lat: Optional[float] = None
    reference_lon: Optional[float] = None
    reference_height: Optional[float] = None
    location: Optional[str] = None
    peta_x: Optional[float] = None
    peta_y: Optional[float] = None

class StationResponse(BaseModel):
    id: str
    name: str
    type: str
    reference_lat: Optional[float]
    reference_lon: Optional[float]
    reference_height: Optional[float]
    location: Optional[str]
    peta_x: Optional[float]
    peta_y: Optional[float]
    
    class Config:
        from_attributes = True

# --- API Contract schemas matching React UI ---

class MapPosition(BaseModel):
    x: float
    y: float

class RoverSchema(BaseModel):
    deviceId: str
    nama: str
    lokasi: str
    ts: int # Epoch milliseconds
    latitude: float
    longitude: float
    altitude_m: float
    east_mm: float
    north_mm: float
    up_mm: float
    horizontal_mm: float
    displacement_3d_mm: float
    movement_indicator_mm: float
    movement_status: str # 'AMAN' | 'WASPADA' | 'BAHAYA' | 'TIDAK_DAPAT_DINILAI'
    connectivity_status: str # 'ONLINE' | 'OFFLINE'
    battery_status: str # 'NORMAL' | 'RENDAH' | 'KRITIS'
    battery_voltage: float
    fix_type: str # 'RTK_FIX' | 'RTK_FLOAT' | 'NO_FIX'
    satellites_active: int
    hdop: float
    data_terpercaya: bool
    peta: MapPosition

class AlarmSchema(BaseModel):
    id: str
    severity: str # 'BAHAYA' | 'WASPADA' | 'INFORMASI'
    deviceId: str
    rover: str
    ts: int # Epoch milliseconds
    judul: str
    deskripsi: str
    detail: str
    status: str # 'AKTIF'

class LokasiSchema(BaseModel):
    nama: str
    status: str
    rover_total: int
    online: int
    offline: int
    alarm_aktif: int
    ts_terbaru: Optional[int] # Epoch milliseconds
    basi: bool

class DashboardResponse(BaseModel):
    mode: str = "LIVE"
    lokasi: LokasiSchema
    rovers: List[RoverSchema]
    alarms: List[AlarmSchema]
    diambil_pada: int # Epoch milliseconds

# --- History schemas ---

class HistoryPoint(BaseModel):
    ts: int # Epoch milliseconds
    east_mm: float
    north_mm: float
    up_mm: float

class HistoryResponse(BaseModel):
    deviceId: str
    rentang: str # '1j' | '6j' | '24j' | '7h' | '30h'
    satuan: str = "mm"
    interval_menit: int
    titik: List[HistoryPoint]
