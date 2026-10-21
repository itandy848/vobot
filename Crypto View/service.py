import random
import arequests as request

_USE_SIMULATED_DATA = False # Whether to use simulated stock information

url_base = "https://api.kraken.com"

_stock_trends = {}
_TREND_LIMIT = 100

def generate_mock_stock_info(symbols):
    # Generate simulated stock information
    res = {"stocks": []}
    for symbol in symbols:
        item = {
            'previousClose': random.randint(400, 450),
            'currentPrice': random.randint(400, 450),
            'currency': 'USD'
        }
        item["symbol"], item["shortName"] = symbol.split(":")
        res["stocks"].append(item)
    return res

async def get_stock_details(symbols):
    global _stock_trends

    # Fetch crypto details information
    details = []
    if not symbols: return details

    if _USE_SIMULATED_DATA:
        res = generate_mock_stock_info(symbols)
    else:
        res = await get_price_from_ticker(symbols)

    for index, item in enumerate(res.get("stocks", [])):
        # No symbol field in data? Get from symbols
        if item.get("symbol", None) is None:
            item["symbol"], item["shortName"] = symbols[index].split(":")

        # update trends
        if item['symbol'] in _stock_trends:
            if len(_stock_trends[item['symbol']]) == _TREND_LIMIT:
                _stock_trends[item['symbol']].pop(0)
            _stock_trends[item['symbol']].append(item['currentPrice'])
        else:
            _stock_trends[item['symbol']] = [item['currentPrice']]
        item['trend'] = _stock_trends[item['symbol']]

        details.append(item)

    return details

# Kraken API related methods

async def get_price_from_ticker(symbols):
    payload = {}
    params = {
        'pair': ",".join(symbols),
        'assetVersion': 1,
    }

    response = await send_kraken_request("GET", "/0/public/Ticker", payload=payload, params=params)
    res = []
    if response and not response['error']:
        result = response['result']
        for k, v in result.items():
            res.append({
                'previousClose': float(v['o']),
                'shortName': k.split("/")[0],
                'currentPrice': float(v['c'][0]),
                'currency': k.split("/")[1],
                'symbol': k.split("/")[0]
            })
    else:
        if 'error' in response:
            print("error: {}".format(response['error']))
    return {'stocks': res}

async def send_kraken_request(method, api, payload, params):
    try:
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        if params:
            api += "?" + "&".join("{}={}".format(k,v ) for k,v in params.items())

        response = await request.request(method, url_base + api, headers=headers, data=payload)
        if response.status_code == 200:
            res = await response.json()
            return res
        else:
            return {}
    except Exception as e:
        print("{}".format(e))
