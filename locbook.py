# 3rd party javascripts
# https://github.com/Leaflet/Leaflet.heat
# https://github.com/perliedman/leaflet-realtime
# https://github.com/Leaflet/Leaflet

# 3rd party packages
# https://github.com/isagalaev/ijson
# https://github.com/frewsxcv/python-geojson

# Standard packages
import argparse
import datetime
import json
import logging
import pickle
from http.server import HTTPServer, BaseHTTPRequestHandler

# 3rd party packages
import geojson as gj
import ijson.backends.yajl2_cffi as ijson

parser = argparse.ArgumentParser()
parser.add_argument("--import_google", "-i", help='Import Google location history JSON file and quit')
parser.add_argument("--export_geojson", "-e", help='Export location history as GeoJSON file and quit')
parser.add_argument("--port", "-p", help='Port to listen on for Owntracks POST requests, default 9001', default=9001)
parser.add_argument("--logfile", "-l", help='If specified, log to file, otherwise log to terminal')
args = parser.parse_args()

history = dict()

# Defaults
js_filename = 'map.js'
history_filename = 'history.pickle'
geojson_filename = 'realtime.geojson'
precision = 4  # Only 4 or 5 make sense for phone data
blur = 5
port = args.port

# Only log to file if argument is present
logging.basicConfig(filename=args.logfile, level=logging.DEBUG, format='%(asctime)s %(message)s') 


class RequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        request_headers = self.headers
        content_length = int(request_headers['Content-Length'])
        parse_msg(self.rfile.read(content_length))
        self.send_response(200)
        self.end_headers() 

    def log_message(self, f, **kwargs):
        # We don't need http.server to run its own log
        return 


def load_history():
    global history
    # Load history from pickle file
    logging.info('Loading history from ' + history_filename)
    try: 
        history = pickle.load(open(history_filename, 'rb'))
        logging.info('History size: ' + str(len(history)) + ' points')   
    except FileNotFoundError:
        logging.info('History not found, creating new file ' + history_filename)
        pass


def parse_msg(msg):
    data = json.loads(msg.decode("utf-8"))
    if data['_type'] == 'location':
        lon = round(data['lon'], precision)
        lat = round(data['lat'], precision)

        point = (lon, lat)
        date, time = tst_to_dt(data['tst'])
        make_history(point, date, time, True)

        logging.info('Location update from device ' + data['tid'] + ': ' + json.dumps(data))
        write_js()
        popup_content = 'Device: ' + data['tid'] + '<br>Date: ' + date + '<br>Time: ' + time
        write_geojson(point, popup_content, geojson_filename)


def make_history(point, date, time, sour):
    global history
    # Defaultdict of defaultdicts
    if point in history:
        if date in history[point]:
            history[point][date].append(time)
        else:
            history[point][date] = [time]
    else:
        history[point] = dict()
        history[point][date] = [time]

    if sour:
        pickle.dump(history, open('history.pickle', 'wb'))


def export_geojson(filename):
    global history
    logging.info('Exporting to ' + filename)
    with open(filename, 'w') as f:
        features = list()
        for point, dt in history.items():
            properties = dict()
            for date, time in dt.items():
                properties[date] = time
            features.append(gj.Feature(geometry=gj.Point(point), properties=properties))
        f.write(gj.dumps(gj.FeatureCollection(features)))
    f.close()


def write_geojson(p, popup_content, filename):
    with open(filename, 'w') as f:
        properties = {'popupContent': popup_content}
        features = [gj.Feature(geometry=gj.Point(p), properties=properties)]
        f.write(gj.dumps(gj.FeatureCollection(features)))
    f.close()


def import_google(filename):
    logging.info('Importing from ' + filename)
    # Needs to be rb!
    with open(filename, 'rb') as f:
        data = ijson.items(f, 'locations.item')
        i = 0
        for o in data:
            i += 1
            point = (round(o['longitudeE7']/10000000, precision), round(o['latitudeE7']/10000000, precision))
            date, time = tst_to_dt(int(o['timestampMs'][:-3]))
            make_history(point, date, time, False)
    f.close()
    logging.info(str(i) + ' items imported from ' + filename)
    logging.info('History size: ' + str(len(history)) + ' points')
    pickle.dump(history, open('history.pickle', 'wb'))
    write_js()


def tst_to_dt(tst):
    date = datetime.datetime.fromtimestamp(tst).strftime('%Y-%m-%d')
    time = datetime.datetime.fromtimestamp(tst).strftime('%H-%M-%S')
    return date, time


def prec_to_m(prec):
    # https://en.wikipedia.org/wiki/Decimal_degrees
    return 111320 / (10**prec)


def write_js():
    global history
    logging.info('Updating .js file')
    with open(js_filename, 'w') as f:
        f.write('var points = [')
        first = True
        for point, dt in history.items():
            count = 0
            for date, time in dt.items():
                count += len(time)
            if first:
                pv_string = '[' + str(point[1]) + ',' + str(point[0]) + ',' + str(count) + ']'
                first = False
            else:
                pv_string = ',[' + str(point[1]) + ',' + str(point[0]) + ',' + str(count) + ']'
            f.write(pv_string)
        f.write('];')
        f.write('config = {radius: ' + str(prec_to_m(precision)) + ',blur:' + str(blur) + '};')
    f.close()


def serve():
    server = HTTPServer(('', port), RequestHandler)
    server.serve_forever()  # Run the HTTP server


def main():
    load_history()
    if args.import_google:
        import_google(args.import_google)
        return

    if args.export_geojson:
        export_geojson(args.export_geojson)
        return

    serve()


if __name__ == "__main__":
    main()
