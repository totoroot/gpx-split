import sys

# check if Python version is recent enough
if sys.version_info[0] < 3:
    print(sys.version_info)
    raise Exception("Python 3 or a more recent version is required.")

import os
import xml.etree.ElementTree as ET
import datetime

filepath = os.path.dirname(__file__)

def spec_dir(dir_input_data = 'data'):

    # check if directory 'data' exists and prompt if not
    if not os.path.isdir(os.path.join(filepath, dir_input_data)):
        print("No directory '{}' containing input data found.".format(dir_input_data))
        mkdir_data_prompt = ''
        while mkdir_data_prompt not in ['y', 'n']:
            mkdir_data_prompt = input("Create directory? [y]es or [n]o: ")
        if mkdir_data_prompt == 'y':
            print("Creating directory '{}'.".format(dir_input_data))
            os.mkdir(dir_input_data)
            print("Please put input data into newly created directory '{}'.".format(dir_input_data))
            sys.exit()
    return dir_input_data

def spec_file(dir_input_data, filename_gpx = 'default'):

    if not os.path.isfile(os.path.join(filepath, dir_input_data, filename_gpx)):
        list_gpx = []
        for root, dirs, files in os.walk(os.path.join(filepath, dir_input_data)):
            for f in files:
                if f.endswith('.gpx'):
                    list_gpx.append(f)
        # Exit if no input file was found
        if len(list_gpx) == 0:
            print("No GPX file found.")
            sys.exit()
        # Use if just one input file was found
        elif len(list_gpx) == 1:
            filename_gpx = list_gpx[0]
            print("Using GPX input file '{}'.".format(filename_gpx))
        # Otherwise let user choose which file to use
        else:
            print("\nChoose one of the following:")
            print('\n'.join(item for item in list_gpx))
            while filename_gpx not in list_gpx:
                filename_gpx = input("\nChoose GPX input file: ")
            print("Using GPX input file '{}'.".format(filename_gpx))

    return filename_gpx

def split(dir_input_data, filename_gpx):

    # open and parse xml tree from gpx file
    with open(os.path.join(filepath, dir_input_data, filename_gpx), 'rt') as f:
        try:
            xml_tree = ET.parse(f)
        except ET.ParseError:
            sys.exit("GPX file could not be parsed. Exiting now.")

    xml_root = xml_tree.getroot()

    # get namespace from root and register for tree
    if "{" in xml_root.tag:
        xml_namespace = xml_root.tag.split("}", 1)[0].strip('{')
        ET.register_namespace('', xml_namespace)
        xml_trkpt = "{{{}}}trkpt".format(xml_namespace)
        xml_trkseg = "{{{}}}trkseg".format(xml_namespace)
        xml_time = "{{{}}}time".format(xml_namespace)
    else:
        xml_trkpt = 'trkpt'
        xml_trkseg = 'trkseg'
        xml_time = 'time'

    # get text from trkpt/time tags
    trkpt_list = []

    for trkpt in xml_root.iter(xml_trkpt):
        trkpt_list.append(trkpt.find(xml_time).text)

    date_list = []
    time_list = []
    datetime_list = []

    for i in range(len(trkpt_list)):
        date, time = trkpt_list[i].split("T", 2)
        time = time[0:-1]
        date_list.append(date)
        time_list.append(time)
        datetime_list.append(datetime.datetime.strptime(trkpt_list[i], "%Y-%m-%dT%H:%M:%SZ"))

    # exit script if GPX file contains data from more than one day.
    if len(set(date_list)) != 1:
        sys.exit("Cannot compute GPX data from more than one day.")

    print("\nGPX data starts at timestamp: {}".format(time_list[0]))
    print("GPX data ends at timestamp:   {}".format(time_list[-1]))

    # get user input for start time and interval
    print("\nSpecify start time and in which interval data should be split.")

    # prompt for start time and check if it is correctly formatted
    start_time_ok = False
    while not start_time_ok:
        start_time_str = date + ' ' + input("Start time: ")
        try:
            start_time = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
            start_time_ok = True
        except ValueError:
            print("Start time did not have right format. Format has to be HH:MM.")

    # prompt if default interval should be used, otherwise prompt for custom interval
    default_interval = None
    while default_interval not in ['y', 'n']:
        default_interval = input("Use default interval of 15 minutes? [y]es or [n]o: ")
    if default_interval == 'y':
        interval = 15
    elif default_interval == 'n':
        interval_ok = False
        while not interval_ok:
            try:
                interval = int(input("Custom interval in minutes: "))
                if 0 < interval <= 360:
                    interval_ok = True
                else:
                    print("Interval has to be given in minutes between 0 and 360.")
            except ValueError:
                print("Interval has to be an integer between 0 and 360.")

    # get datetime value of interval
    interval_datetime = datetime.timedelta(minutes=interval)
    last_timestamp = datetime_list[-1]
    timestamp = start_time
    timestamp_list = [start_time]

    # get points in time at which data should be split as list
    while timestamp < last_timestamp:
        timestamp += interval_datetime
        timestamp_list.append(timestamp)

    temp_list = []
    flattened_list = []
    splits = []

    # sort datetime instances into splits
    for k in range(1, len(timestamp_list)):
        split_list = []
        for j in range(len(datetime_list)):
            if datetime_list[j] <= timestamp_list[k] and datetime_list[j] not in flattened_list:
                split_list.append(datetime_list[j])
        # use temporary list to avoid datetime duplicates across splits
        # flatten list to make it properly iterable
        temp_list.append(split_list)
        for x in temp_list:
            for y in x:
                flattened_list.append(y)
        # append to final list of splits
        splits.append(split_list)

    # modify tree according to splits and write to FS
    for l in range(len(splits)):
        for trkseg in xml_root.findall('.//{}/..'.format(xml_trkpt)):
            for trkpt in trkseg.findall(xml_trkpt):
                if datetime.datetime.strptime(trkpt.find(xml_time).text, "%Y-%m-%dT%H:%M:%SZ") not in splits[l]:
                    trkseg.remove(trkpt)

        t1 = datetime.datetime.strftime(timestamp_list[l], "%Y-%m-%dT%H:%M:%SZ")
        t2 = datetime.datetime.strftime(timestamp_list[l+1], "%Y-%m-%dT%H:%M:%SZ")
        output = os.path.join(filepath, dir_input_data, '{}_{}.gpx'.format(t1, t2))
        xml_tree.write(output, encoding='UTF-8', xml_declaration='True')

        # parse tree to get original for every split
        with open(os.path.join(filepath, dir_input_data, filename_gpx), 'rt') as f:
            xml_tree = ET.parse(f)
            xml_root = xml_tree.getroot()


def main():
    dir_input_data = spec_dir()
    filename_gpx = spec_file(dir_input_data)
    split(dir_input_data, filename_gpx)

if __name__ == "__main__":
    main()