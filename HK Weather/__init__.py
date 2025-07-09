import lvgl as lv
import arequests
import time
import net
import peripherals

# Name of the App
NAME = "HK Weather"

# App Manager
app_mgr = None

# Screen resolutin
SCR_WIDTH, SCR_HEIGHT = peripherals.screen.screen_resolution

# App Icon
ICON = f'A:apps/{NAME}/resources/hko_logo.png'

CAN_BE_AUTO_SWITCHED = True

# Initialize LVGL objects
scr = None
icon_weather = None
lbl_temp = None
lbl_temp_degree = None
icon_temp_min = None
lbl_temp_min = None
lbl_temp_min_degree = None
icon_temp_max = None
lbl_temp_max = None
lbl_temp_max_degree = None
lbl_humidity = None
lbl_humidity_percent = None
lbl_station = None
lbl_hko_updtime = None
lbl_status_panel = None
lbl_status = None
icon_shelly = None
btn_shelly = None
lbl_shelly_temp = None
lbl_shelly_temp_degree = None
lbl_shelly_humidity = None
lbl_shelly_humidity_precent = None
lbl_shelly_updtime = None
btn_forecast = None
obj_forecast = []

# HKO weather data
station = None
temp = None
temp_updtime = None
humidity = None
humidity_updtime = None
temp_maxmin = None
temp_maxmin_updtime = None
icon_idx = None
icon_updtime = None
forecast_data = None
forecast_updtime = None

# Shelly data
enable_shelly = False
shelly_tc = None
shelly_rh = None
shelly_updtime = None

# states control
pending_retrieval = False
pending_refresh_ui = False

# counters
REFRESH_INTERVAL_MS = 10 * 60 * 1000
PAGE_SWITCH_INTERVAL_MS = 15 * 1000
last_refresh_ticks_ms = None
last_switch_ticks_ms = None

# page control
current_page = 0

# last error message
error_message = ''

# global network timeout
NETWORK_TIMEOUT=15

# No of days to show in forecast panel
MAX_HKO_FORECAST_DAYS=9
DEFAULT_FORECAST_DAYS="6"
forecast_days=DEFAULT_FORECAST_DAYS

# Forecast configurations
forecast_config = {
    "5": {
        "width": 62,
        "weekday_font": lv.font_ascii_bold_18,
        "icon_y": 20,
        "icon_scale": 128,
        "temp_font": lv.font_ascii_18,
        "temp_y": 80,
    },
    "6": {
        "width": 52,
        "weekday_font": lv.font_ascii_bold_18,
        "icon_y": 25,
        "icon_scale": 100,
        "temp_font": lv.font_ascii_18,
        "temp_y": 80,
    },
    "7": {
        "width": 44,
        "weekday_font": lv.font_ascii_bold_18,
        "icon_y": 30,
        "icon_scale": 77,
        "temp_font": lv.font_ascii_14,
        "temp_y": 80,
    },
}

# Default HKO station
DEFAULT_LOCATION = 'Peng Chau'

# API URLs
api_url = {
    'weather': 'https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=en',
    'temperature': 'https://data.weather.gov.hk/weatherAPI/hko_data/regional-weather/latest_1min_temperature.csv',
    'humidity': 'https://data.weather.gov.hk/weatherAPI/hko_data/regional-weather/latest_1min_humidity.csv',
    'temperature_maxmin': 'https://data.weather.gov.hk/weatherAPI/hko_data/regional-weather/latest_since_midnight_maxmin.csv',
    'forecast': 'https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=fnd&lang=en',
}
shelly_url = ''

def format_hko_date(date_str):
    return "{}-{}-{} {}:{}:00".format(date_str[:4], date_str[4:6], date_str[6:8], date_str[8:10], date_str[10:12])

def round_text(text):
    try:
        return "{:.0f}".format(round(float(text))) if text else ""
    except:
        return "0"

def set_status(message, error=False, source=""):
    global error_message

    if scr:
        if error or not message:
            error_message = message

        if message is None or message == "":
            lbl_status_panel.add_flag(lv.obj.FLAG.HIDDEN)
        else:
            lbl_status.set_style_text_color(lv.palette_main(lv.PALETTE.RED) if error else lv.color_white(), lv.PART.MAIN)
            lbl_status.set_text("{}{}".format(f"({source}) " if source else "", message))
            lbl_status_panel.remove_flag(lv.obj.FLAG.HIDDEN)

def csv_get_value(csv, key):
    lines = csv.split('\n')
    for line in lines:
        if line:
            fields = line.split(',')
            if fields[1] == key:
                return fields

def get_hko_proper_time(time):
    return time.replace('T', ' ').replace('+08:00', '')

async def get_weather_icon():
    icon = ''
    icon_time = ''

    data = await get_hko_weather_json(api_url['weather'])
    if data and 'icon' in data:
        icon = data['icon'][0]
        icon_time = get_hko_proper_time(data['iconUpdateTime'])

    return icon, icon_time

async def get_forecast_data():
    weather_data = None
    weather_time = ''

    fields = ['forecastDate', 'week', 'forecastMaxtemp', 'forecastMintemp', 'forecastMaxrh', 'forecastMinrh',
              'ForecastIcon']

    data = await get_hko_weather_json(api_url['forecast'])
    if data and all(k in data for k in ('weatherForecast','updateTime')):
        weather_data = []
        for day in range(MAX_HKO_FORECAST_DAYS):
            weather_data.append({})
            for field in fields:
                weather_data[day][field] = data['weatherForecast'][day].get(field, '')
        weather_time = get_hko_proper_time(data['updateTime'])

    return weather_data, weather_time

async def get_hko_weather_json(url):
    data = None

    if net.connected():
        resp = None
        try:
            resp = await arequests.get(url, timeout=NETWORK_TIMEOUT)
            if resp.status_code == 200:
                data = await resp.json()
        except Exception as e:
            raise Exception("URL:{} - {}".format(url, e))
        finally:
            if resp:
                resp.close()

    return data

async def get_hko_location_csv_values(url, kpi_pos, time_pos):
    kpi = None
    kpi_time = None

    if net.connected():
        resp = None
        try:
            resp = await arequests.get(url, timeout=NETWORK_TIMEOUT)
            if resp.status_code == 200:
                fields = csv_get_value(await resp.text, station)
                if fields:
                    if type(kpi_pos) is list:
                        kpi = []
                        for pos in kpi_pos:
                            if pos < len(fields):
                                if fields[pos] is None:
                                    raise Exception("Empty data in CSV")
                                kpi += fields[pos],
                            else:
                                kpi += '',
                    else:
                        if fields[kpi_pos] is None:
                            raise Exception("Empty data in CSV")
                        kpi = fields[kpi_pos]
                    kpi_time = format_hko_date(fields[time_pos])
        except Exception as e:
            raise Exception("URL:{} - {}".format(url, e))
        finally:
            if resp:
                resp.close()
    return kpi, kpi_time

async def get_shelly_data():
    data = None

    if net.connected():
        resp = None
        try:
            resp = await arequests.get(shelly_url, timeout=NETWORK_TIMEOUT)
            if resp.status_code == 200:
                data = str(await resp.text).split(',')
        except Exception as e:
            raise Exception("URL:{} - {}".format(shelly_url, e))
        finally:
            if resp:
                resp.close()
    return data

async def retrieve_data():
    global icon_idx, icon_updtime, temp, temp_updtime, temp_maxmin, temp_maxmin_updtime, humidity, humidity_updtime
    global forecast_data, forecast_updtime
    global last_refresh_ticks_ms
    global pending_retrieval
    global pending_refresh_ui
    global shelly_tc, shelly_rh, shelly_updtime

    pending_retrieval = False

    try:
        # get HKO data
        new_temp, new_temp_updtime = await get_hko_location_csv_values(api_url['temperature'], 2, 0)
        new_humidity, new_humidity_updtime = await get_hko_location_csv_values(api_url['humidity'], 2, 0)
        new_temp_maxmin, new_temp_maxmin_updtime = await get_hko_location_csv_values(api_url['temperature_maxmin'], [2,3], 0)
        new_icon_idx, new_icon_updtime = await get_weather_icon()
        new_forecast_data, new_forecast_updtime = await get_forecast_data()

        # get Shelly data
        if enable_shelly:
            shelly_data = await get_shelly_data()
            if shelly_data:
                shelly_tc = shelly_data[0]
                shelly_rh = shelly_data[1]
                shelly_updtime = shelly_data[2][-8:]

        # update global var all at once
        temp, temp_updtime = new_temp, new_temp_updtime
        humidity, humidity_updtime = new_humidity, new_humidity_updtime
        temp_maxmin, temp_maxmin_updtime = new_temp_maxmin, new_temp_maxmin_updtime
        icon_idx, icon_updtime = new_icon_idx, new_icon_updtime
        forecast_data, forecast_updtime = new_forecast_data, new_forecast_updtime

        # all data is ready
        pending_refresh_ui = True
        set_status(None)
        last_refresh_ticks_ms = time.ticks_ms()

        return True
    except Exception as e:
        set_status("{}, {}".format(type(e).__name__, e.args), True, "retrieve_data()")
        last_refresh_ticks_ms = time.ticks_ms()
        return False

def update_ui():
    global pending_refresh_ui

    try:
        # weather icon
        icon_weather.set_src(f'A:apps/{NAME}/resources/pic{icon_idx}.png')

        # temperature
        lbl_temp.set_text(round_text(temp))

        # minimum and maximum temperature
        if temp_maxmin:
            lbl_temp_min.set_text(round_text(temp_maxmin[1]))
            lbl_temp_max.set_text(round_text(temp_maxmin[0]))

        # humidity
        lbl_humidity.set_text("{}".format(humidity))

        # HKO station
        lbl_station.set_text(station)

        # HKO update status
        lbl_hko_updtime.set_text(temp_updtime[-8:])

        if current_page == 1 or not enable_shelly:
            if enable_shelly:
                # show forecast page
                btn_shelly.add_flag(lv.obj.FLAG.HIDDEN)
                btn_forecast.remove_flag(lv.obj.FLAG.HIDDEN)

            # if len(obj_forecast) == len(forecast_data) == int(forecast_days):
            for i in range(int(forecast_days)):
                if 'week' in obj_forecast[i] and 'week' in forecast_data[i]:
                    obj_forecast[i]['week'].set_text(forecast_data[i]['week'][0:3])
                    obj_forecast[i]['icon'].set_src(
                        'A:apps/{}/resources/pic{}.png'.format(NAME, forecast_data[i]['ForecastIcon']))
                    obj_forecast[i]['icon'].set_scale(forecast_config[forecast_days]['icon_scale'])
                    obj_forecast[i]['temp'].set_text("{}-{}".format(forecast_data[i]['forecastMintemp']['value'],
                                                                    forecast_data[i]['forecastMaxtemp']['value']))
        else:
            # show Shelly page
            btn_shelly.remove_flag(lv.obj.FLAG.HIDDEN)
            btn_forecast.add_flag(lv.obj.FLAG.HIDDEN)

            # Shelly status
            lbl_shelly_temp.set_text(round_text(shelly_tc))
            lbl_shelly_humidity.set_text("{}".format(round_text(shelly_rh)))
            lbl_shelly_updtime.set_text(shelly_updtime)
    except Exception as e:
        set_status("{}, {}".format(type(e).__name__, e.args), True, "update_ui()")

    pending_refresh_ui = False

def get_settings_json():
    return {
        "title": "HK Weather app settings",
        "form": [
            # Station dropdown
            {
                "type": "select",
                "default": DEFAULT_LOCATION,
                "caption": "HKO Station",
                "name": "station",
                "options": [
                    ("Chek Lap Kok", "Chek Lap Kok"),
                    ("Cheung Chau", "Cheung Chau"),
                    ("Clear Water Bay", "Clear Water Bay"),
                    ("Happy Valley", "Happy Valley"),
                    ("HK Observatory", "HK Observatory"),
                    ("HK Park", "HK Park"),
                    ("Kai Tak Runway Park", "Kai Tak Runway Park"),
                    ("Kau Sai Chau", "Kau Sai Chau"),
                    ("King's Park", "King's Park"),
                    ("Kowloon City", "Kowloon City"),
                    ("Kwun Tong", "Kwun Tong"),
                    ("Lau Fau Shan", "Lau Fau Shan"),
                    ("Ngong Ping", "Ngong Ping"),
                    ("Pak Tam Chung", "Pak Tam Chung"),
                    ("Peng Chau", "Peng Chau"),
                    ("Sai Kung", "Sai Kung"),
                    ("Sha Tin", "Sha Tin"),
                    ("Sham Shui Po", "Sham Shui Po"),
                    ("Shau Kei Wan", "Shau Kei Wan"),
                    ("Shek Kong", "Shek Kong"),
                    ("Sheung Shui", "Sheung Shui"),
                    ("Stanley", "Stanley"),
                    ("Ta Kwu Ling", "Ta Kwu Ling"),
                    ("Tai Lung", "Tai Lung"),
                    ("Tai Mei Tuk", "Tai Mei Tuk"),
                    ("Tai Mo Shan", "Tai Mo Shan"),
                    ("Tai Po", "Tai Po"),
                    ("Tate's Cairn", "Tate's Cairn"),
                    ("The Peak", "The Peak"),
                    ("Tseung Kwan O", "Tseung Kwan O"),
                    ("Tsing Yi", "Tsing Yi"),
                    ("Tsuen Wan Ho Koon", "Tsuen Wan Ho Koon"),
                    ("Tsuen Wan Shing Mun Valley", "Tsuen Wan Shing Mun Valley"),
                    ("Tuen Mun", "Tuen Mun"),
                    ("Waglan Island", "Waglan Island"),
                    ("Wetland Park", "Wetland Park"),
                    ("Wong Chuk Hang", "Wong Chuk Hang"),
                    ("Wong Tai Sin", "Wong Tai Sin"),
                    ("Yuen Long Park", "Yuen Long Park")
                ]
            },
            {
                "type": "radio",
                "default": DEFAULT_FORECAST_DAYS,
                "caption": "No of days to show in weather forecast",
                "name": "forecast_days",
                "options": [("5 Days", "5"), ("6 Days", "6"), ("7 Days", "7")],
            },
            {
                "type": "input",
                "default": "",
                "caption": "Indoor sensor URL:",
                "name": "shelly_url",
                "attributes": {"placeholder": "Enter your indoor sensor URL"}
            },
        ]
    }

def switch_page():
    global last_switch_ticks_ms
    global pending_refresh_ui
    global current_page

    current_page = 0 if current_page == 1 else 1
    pending_refresh_ui = True
    last_switch_ticks_ms = time.ticks_ms()

def event_handler(event):
    global last_refresh_ticks_ms

    e_code = event.get_code()
    if e_code == lv.EVENT.KEY:
        e_key = event.get_key()
        if e_key == lv.KEY.ENTER:
            last_refresh_ticks_ms = None
        elif e_key in (lv.KEY.RIGHT, lv.KEY.LEFT):
            switch_page()
    elif e_code == lv.EVENT.FOCUSED:
        if not lv.group_get_default().get_editing():
            lv.group_get_default().set_editing(True)

async def on_boot(apm):
    global app_mgr
    app_mgr = apm

async def on_running_foreground():
    """Called when the app is active, approximately every 200ms."""

    global last_switch_ticks_ms
    global pending_retrieval
    global pending_refresh_ui
    global current_page

    if pending_retrieval:
        await retrieve_data()
    elif pending_refresh_ui:
        update_ui()
    elif last_refresh_ticks_ms is None or time.ticks_diff(time.ticks_ms(), last_refresh_ticks_ms) > REFRESH_INTERVAL_MS:
        set_status("Retrieving network data...")
        pending_retrieval = True
    elif enable_shelly and last_switch_ticks_ms and time.ticks_diff(time.ticks_ms(),
                                                                        last_switch_ticks_ms) > PAGE_SWITCH_INTERVAL_MS:
        switch_page()

async def on_resume():
    if last_refresh_ticks_ms:
        update_ui()

async def on_stop():
    global scr

    if scr:
        scr.clean()
        scr.delete_async()
        scr = None

async def on_start():
    global scr
    global station
    global forecast_days
    global shelly_url
    global enable_shelly
    global last_refresh_ticks_ms
    global last_switch_ticks_ms
    global pending_refresh_ui

    # top panel objects
    global icon_weather, lbl_temp, lbl_temp_degree, icon_temp_min, lbl_temp_min, lbl_temp_min_degree, icon_temp_max, lbl_temp_max, lbl_temp_max_degree
    global lbl_humidity, lbl_humidity_percent
    global lbl_station, lbl_hko_updtime

    # status objects
    global lbl_status_panel, lbl_status

    # shelly objects
    global btn_shelly, lbl_shelly_temp, lbl_shelly_humidity, lbl_shelly_updtime

    # forecast objects
    global btn_forecast

    # get settings
    s = app_mgr.config()
    new_station = s.get("station", DEFAULT_LOCATION)
    new_forecast_days = s.get("forecast_days", DEFAULT_FORECAST_DAYS)
    new_shelly_url = s.get("shelly_url", "")
    if new_station != station:
        # force a data retrieval if station is changed
        last_refresh_ticks_ms = None
    elif new_forecast_days != forecast_days:
        # force a UI refresh if forecast_days is changed
        pending_refresh_ui = True
    if new_shelly_url:
        if new_shelly_url != shelly_url:
            # force a data retrieval if shelly_url is changed
            last_refresh_ticks_ms = None
        enable_shelly = True
    else:
        if new_shelly_url != shelly_url:
            # force a UI refresh if shelly_url is empty
            pending_refresh_ui = True
        enable_shelly = False

    forecast_days = new_forecast_days
    station = new_station
    shelly_url = new_shelly_url
    last_switch_ticks_ms = time.ticks_ms()

    # Create and initialize LVGL widgets
    scr = lv.obj()

    """ Top panel
    """
    # weather icon
    icon_weather = lv.image(scr)
    icon_weather.set_pos(0, 0)

    # temperature
    lbl_temp = lv.label(scr)
    lbl_temp.set_pos(120, 15)
    lbl_temp.set_style_text_font(lv.font_ascii_bold_48, 0)
    lbl_temp.set_style_text_color(lv.palette_main(lv.PALETTE.BLUE),lv.PART.MAIN)

    lbl_temp_degree = lv.label(scr)
    lbl_temp_degree.set_text("°C")
    lbl_temp_degree.set_pos(180, 20)
    lbl_temp_degree.set_style_text_font(lv.font_ascii_bold_28, 0)

    lbl_humidity = lv.label(scr)
    lbl_humidity.set_pos(227, 15)
    lbl_humidity.set_style_text_font(lv.font_ascii_bold_48, 0)
    lbl_humidity.set_style_text_color(lv.palette_main(lv.PALETTE.GREEN),lv.PART.MAIN)

    lbl_humidity_percent = lv.label(scr)
    lbl_humidity_percent.set_text("%")
    lbl_humidity_percent.set_pos(282, 20)
    lbl_humidity_percent.set_style_text_font(lv.font_ascii_bold_28, 0)

    # minimum and maximum temperature
    icon_temp_min = lv.image(scr)
    icon_temp_min.set_src(f'A:apps/{NAME}/resources/icon_wea_arrowdown.png')
    icon_temp_min.set_pos(130, 80)

    lbl_temp_min = lv.label(scr)
    lbl_temp_min.set_pos(150, 75)
    lbl_temp_min.set_style_text_font(lv.font_ascii_bold_22, 0)
    lbl_temp_min.set_style_text_color(lv.palette_main(lv.PALETTE.YELLOW), lv.PART.MAIN)

    lbl_temp_min_degree = lv.label(scr)
    lbl_temp_min_degree.set_text("°C")
    lbl_temp_min_degree.set_pos(177, 75)
    lbl_temp_min_degree.set_style_text_font(lv.font_ascii_bold_18, 0)

    icon_temp_max = lv.image(scr)
    icon_temp_max.set_src(f'A:apps/{NAME}/resources/icon_wea_arrowup.png')
    icon_temp_max.set_pos(210, 80)

    lbl_temp_max = lv.label(scr)
    lbl_temp_max.set_pos(230, 75)
    lbl_temp_max.set_style_text_font(lv.font_ascii_bold_22, 0)
    lbl_temp_max.set_style_text_color(lv.palette_main(lv.PALETTE.YELLOW), lv.PART.MAIN)

    lbl_temp_max_degree = lv.label(scr)
    lbl_temp_max_degree.set_text("°C")
    lbl_temp_max_degree.set_pos(257, 75)
    lbl_temp_max_degree.set_style_text_font(lv.font_ascii_bold_18, 0)

    # station
    lbl_station = lv.label(scr)
    lbl_station.set_pos(0, 110)
    lbl_station.set_style_text_font(lv.font_ascii_14, 0)

    # HKO update time
    lbl_hko_updtime = lv.label(scr)
    lbl_hko_updtime.set_pos(257, 110)
    lbl_hko_updtime.set_style_text_font(lv.font_ascii_14, 0)

    """ Shelly panel
    """
    # shelly section
    if enable_shelly:
        btn_shelly = lv.button(scr)
        btn_shelly.set_pos(0, 130)
        btn_shelly.set_size(SCR_WIDTH, 110)
        btn_shelly.set_style_pad_all(0, lv.PART.MAIN)
        btn_shelly.set_style_bg_color(lv.color_hex(0x1e5eb3), lv.PART.MAIN)

        # home icon
        icon_home = lv.image(btn_shelly)
        icon_home.set_pos(10, 15)
        icon_home.set_src(f'A:apps/{NAME}/resources/indoor_icon.png')

        lbl_shelly_temp = lv.label(btn_shelly)
        lbl_shelly_temp.set_pos(120, 15)
        lbl_shelly_temp.set_style_text_font(lv.font_ascii_bold_48, 0)

        lbl_shelly_temp_degree = lv.label(btn_shelly)
        lbl_shelly_temp_degree.set_text("°C")
        lbl_shelly_temp_degree.set_pos(180, 20)
        lbl_shelly_temp_degree.set_style_text_font(lv.font_ascii_bold_28, 0)

        lbl_shelly_humidity = lv.label(btn_shelly)
        lbl_shelly_humidity.set_pos(227, 15)
        lbl_shelly_humidity.set_style_text_font(lv.font_ascii_bold_48, 0)

        lbl_shelly_humidity_degree = lv.label(btn_shelly)
        lbl_shelly_humidity_degree.set_text("%")
        lbl_shelly_humidity_degree.set_pos(282, 20)
        lbl_shelly_humidity_degree.set_style_text_font(lv.font_ascii_bold_28, 0)

        icon_shelly = lv.image(btn_shelly)
        icon_shelly.set_src(f'A:apps/{NAME}/resources/shelly_icon.png')
        icon_shelly.set_pos(120, 80)

        lbl_shelly_updtime = lv.label(btn_shelly)
        lbl_shelly_updtime.set_pos(257, 92)
        lbl_shelly_updtime.set_style_text_font(lv.font_ascii_14, 0)

    """ Forecast panel
    """
    # forecast section
    btn_forecast = lv.button(scr)
    btn_forecast.set_pos(0, 130)
    btn_forecast.set_size(SCR_WIDTH, 110)
    btn_forecast.set_style_pad_all(5, lv.PART.MAIN)
    btn_forecast.set_style_bg_color(lv.color_hex(0x1e5eb3), lv.PART.MAIN)

    # weekday objects
    global obj_forecast
    obj_forecast = []
    for i in range(int(forecast_days)):
        offset = round((SCR_WIDTH - 10) / int(forecast_days))

        btn_weekday = lv.button(btn_forecast)
        btn_weekday.set_pos(i * offset, 0)
        btn_weekday.set_size(forecast_config[forecast_days]['width'], 100)
        btn_weekday.set_style_radius(0, 0)
        btn_weekday.set_style_pad_all(0, lv.PART.MAIN)
        btn_weekday.set_style_bg_color(lv.color_hex(0x1e5eb3 if i % 2 == 0 else 0x277beb), lv.PART.MAIN)

        lbl_week = lv.label(btn_weekday)
        lbl_week.set_style_text_font(forecast_config[forecast_days]['weekday_font'], 0)
        lbl_week.align(lv.ALIGN.TOP_MID, 0, 0)

        icon_week = lv.image(btn_weekday)
        icon_week.align(lv.ALIGN.TOP_MID, 0, forecast_config[forecast_days]['icon_y'])
        icon_week.set_size(forecast_config[forecast_days]['width'], forecast_config[forecast_days]['width'])

        lbl_temp_range = lv.label(btn_weekday)
        lbl_temp_range.set_style_text_font(forecast_config[forecast_days]['temp_font'], 0)
        lbl_temp_range.align(lv.ALIGN.TOP_MID, 0, forecast_config[forecast_days]['temp_y'])

        obj_forecast.append({
            'week': lbl_week,
            'icon': icon_week,
            'temp': lbl_temp_range,
        })

    # toggle Shelly/forecast panel
    if enable_shelly:
        if current_page == 0:
            btn_shelly.remove_flag(lv.obj.FLAG.HIDDEN)
            btn_forecast.add_flag(lv.obj.FLAG.HIDDEN)
        else:
            btn_shelly.add_flag(lv.obj.FLAG.HIDDEN)
            btn_forecast.remove_flag(lv.obj.FLAG.HIDDEN)

    # status
    lbl_status_panel = lv.button(scr)
    lbl_status_panel.set_pos(0, 205)
    lbl_status_panel.set_size(SCR_WIDTH, 35)
    lbl_status_panel.set_style_radius(0,0)
    lbl_status_panel.set_style_pad_all(3, lv.PART.MAIN)
    lbl_status_panel.set_style_bg_color(lv.color_hex(0x0), lv.PART.MAIN)
    lbl_status_panel.set_style_bg_opa(200, lv.PART.MAIN)

    lbl_status = lv.label(lbl_status_panel)
    lbl_status.set_width(SCR_WIDTH)
    lbl_status.align(lv.ALIGN.CENTER, 0, 0)
    lbl_status.set_long_mode(lv.label.LONG.SCROLL_CIRCULAR)
    lbl_status.set_style_text_font(lv.font_ascii_bold_18, 0)

    set_status(error_message, error_message, "on_start()")

    lv.scr_load(scr)

    # register key event handler
    scr.add_event(event_handler, lv.EVENT.ALL, None)

    # set focus to default group so as to receive key events properly
    group = lv.group_get_default()
    if group:
        group.add_obj(scr)
        lv.group_focus_obj(scr)
        group.set_editing(True)
