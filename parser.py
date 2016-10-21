import BeautifulSoup
from operator import itemgetter
from xml.etree import ElementTree
import datetime
import urllib2
import xlwt
import copy
import sys
import csv
import os
import logging 
import argparse

"""
These functions are used to collect SWOB-ML data from the Environment Canada
Datastore.  The data can be organized into CSV and Excel formats using the function within.

See the 'main' section of this file for examples
"""

urlroot = "http://dd.weather.gc.ca/observations/swob-ml/"
logging.basicConfig(filename = 'swob.log', format='[%(asctime)s] [%(levelname)s] line=%(lineno)s module=%(module)s function=%(funcName)s [%(message)s]', 
    datefmt = '%a, %d %b %Y %H:%M:$S', level = logging.DEBUG)

if not os.path.isfile("swob.log"):
    open("swob.log","w")
    close("swob.log")
def get_html_string(url):
    """
    Gets the html string from a url
    :param url: (str) the url to get html from
    :returns: (str) the string representation of the html at a url
    """
    catcher = 0
    while(catcher <3):
        try:
            URLObj = urllib2.urlopen(url)
            html_string = URLObj.read().decode('utf-8')
            catcher=3
            return html_string
        except urllib2.URLError as err:
	    logging.error(str(err) + ': ' + url)
            print "Link retrieval error on:"
            print url
            html_string = ""
            catcher+=1
            if(catcher==3):
                return html_string
            else:
                print "Trying again"

def get_stations_list(urlroot, strdate):
    """
    Returns a list of the all stations for which swob-ml observations are available
    :param urlroot: (str) the root url to base searches from 
    :param strdate: (str) the date string in YYYYMMDD format
    :returns: (list) of str with 3 letter station designations
    """
    all_stations_list = []
    all_stations_html = get_html_string(urlroot+strdate+"/")
    all_stations_soup = BeautifulSoup.BeautifulSoup(all_stations_html)

    for tag in all_stations_soup.findAll('a', href=True):
        #length is 5: eg. "CVSL/", we remove the "/" to get station name
        if tag['href'].__len__() == 5:
            tag['href'] = tag['href'].replace("/","")
            tag['href'] = tag['href'][1:].encode('ascii','ignore')
            all_stations_list.append(tag['href'])
    
    return all_stations_list

def clean_incoming(clean_info_filename="in.txt"):
    """
    Creates an index from which to sort data.  Indexable by field_name and includes whether or not to override
    field_name with a human specified readable field name and desired order.
    :param clean_info_filename: (str optional) the filename of the text file to use for creating the output dictionary
           This file should be formated with csv data as such: 
           "fieldx_name, Readable Field Name, (int) order\n
            fieldx+1_name, Readable Field Name, (int) order\n" where each 3 value sequence represents
           a field and is on its own line.
           Default: 'in.txt'
    :param default_order: (int optional) the desired default order for fields to appear in outputs in.
           Default: 500
    :returns: (dict, bool) where the dict is a dictionary of 
           {"field_name":["Readable Field Name",(int) Priority],...} format
           The bool returned is True if data should be cleaned using this information, or False otherwise
    """
    try:
        clean_info = {}
        clean_info_file_obj = file(clean_info_filename,'rb')
        split = csv.reader(clean_info_file_obj, delimiter=',', skipinitialspace=True)
        clean_info["date_tm"] = ["Date and Time", 0]
        clean_info["stn_nam"] = ["Station Name", 2]
        clean_info["tc_id"] = ["TC Indentifier", 4]
	clean_info["wmo_synop_id"] = ["WMO Synoptic Identifier", 6]
	clean_info["clim_id"] = ["Climate Identifier", 8]
	counter = 10
	title = ["date_tm","stn_nam","tc_id","wmo_synop_id","clim_id"] 
        for line_data_list in split:
            if line_data_list.__len__()<=3:
                clean = True
                clean_info[line_data_list[0]]=[line_data_list[1],counter]
                counter = counter + 2
		title.append(line_data_list[0])
	
    except Exception, err:
        clean = False
        if clean_info_filename != "OFF":
	    logging.error("Can't read file passed to clean_incoming: " + str(err))
            print "Can't read file passed to clean_incoming(): " + str(err)
    
    return clean_info, clean, title

def parse_xml_links(link_base_url_root, xml_links, title_dict={}, clean_dict={}, clean=False, default_order=500):
    """
    Parse xml links and collect data from those links
    :param link_base_url_root: (str) the base url from which to add all links
    :param xml_links: (list) of str such that each value is a link to an xml that can be added to link_base_url_root
    :param title_dict: (dict optional) a dictionary in {'field' : [order,uom],...} format for later formatting of field names
           Default: {}
    :param clean_dict: (dict optional) a dictionary of 
           {"field_name":["Readable Field Name",(int) Priority],...} format
           Default: {}
    :param clean: (bool optional) True if data should be cleaned using clean_dict, or False otherwise
           Default: False
    :param default_order: (int optional) the desired default order for fields to appear in outputs in.
           Default: 500
    :returns: (list, list) a list of dicts where each dict is the xml data from one link, and a list of sorted titles
    """
    title_list_sorted = []
    total_xml_data = []
    for xml_address in xml_links:
        catcher=0
        while(catcher<3):
            try:
                xml_file = urllib2.urlopen(link_base_url_root + xml_address)
                xml_parser_obj = ElementTree.parse(xml_file)
                catcher=3
            except urllib2.URLError as err:
                catcher+=1
                print "Error opening xmladdress" + xml_address
                logging.error(str(err) + ": " + xml_address) 
            lastname = ""
            single_xml_data = {}
            counter = 0
            for node in xml_parser_obj.getiterator():
                name  = node.attrib.get('name')
                value = node.attrib.get('value')
                uom   = unicode(node.attrib.get('uom')).encode('ascii','ignore')
                order = counter
                qual  = ""
                if name == "qa_summary":
                    qual = str(value)
                    single_xml_data[lastname][3] = qual
                else:
                    if clean == True:
                        try:
                            order = counter
                            counter = counter + 1
                        except:
                            pass
                        
                    single_xml_data[name] = [value, uom, order, qual]
                    title_dict[name] = [order, uom]
                    
                lastname = name
            
            total_xml_data.append(single_xml_data)
            title_list_sorted = sorted(title_dict.iteritems(),key=itemgetter(1), reverse=False)
            

    return total_xml_data, title_list_sorted

def parse_station(urlroot, strdate, station, title_dict={}, clean_dict={}, clean=False, default_order=500):
    """
    Parses all station data from a date
    :param urlroot: (str) the url root from which all SWOB-ML dates are listed
    :param strdate: (str) the date in "YYYYMMDD" format to get the station data on
    :param station: (str) the three (or four) character station identifier eg. "VSL"
    :param title_dict: (dict optional) a dictionary in {'field' : [order,uom],...} format for later formatting of field names
           Default: {}
    :param clean_dict: (dict optional) a dictionary of 
           {"field_name":["Readable Field Name",(int) Priority],...} format
           Default: {}
    :param clean: (bool optional) True if data should be cleaned using clean_dict, or False otherwise
           Default: False
    :param default_order: (int optional) the desired default order for fields to appear in outputs in.
           Default: 500
    :returns: (list, list) a list of dicts where each dict is the xml data from one hour at the station, and a list of sorted titles
    """
    if station.__len__() == 3:
        station = "C" + station
    
    one_station_url = urlroot + strdate + "/" + station + "/"
    
    one_station_html = get_html_string(one_station_url)

    one_station_xml_links = []
    one_station_soup = BeautifulSoup.BeautifulSoup(one_station_html)
    for tag in one_station_soup.findAll('a', href=True):
        if ".xml" in tag['href']:
            file_name = tag['href'].encode('ascii','ignore')
            one_station_xml_links.append(file_name)
    
    one_station_data_list, ordered_titles = parse_xml_links(one_station_url, one_station_xml_links, title_dict=title_dict, clean_dict=clean_dict, clean=clean)

    return one_station_data_list, ordered_titles

def parse_station_hourly(urlroot, strdate, hour,station, title_dict={}, clean_dict={}, clean=False, default_order=500):
    """
    Parses all station data from a date on a hourly basis
    :param urlroot: (str) the url root from which all SWOB-ML dates are listed
    :param strdate: (str) the date in "YYYYMMDD" format to get the station data on
    :param hour: (str) the hour in "HH00" format to get the station data
    :param station: (str) the three (or four) character station identifier eg. "VSL"
    :param title_dict: (dict optional) a dictionary in {'field' : [order,uom],...} format for later formatting of field names
           Default: {}
    :param clean_dict: (dict optional) a dictionary of
           {"field_name":["Readable Field Name",(int) Priority],...} format
           Default: {}
    :param clean: (bool optional) True if data should be cleaned using clean_dict, or False otherwise
           Default: False
    :param default_order: (int optional) the desired default order for fields to appear in outputs in.
           Default: 500
    :returns: (list, list) a list of dicts where each dict is the xml data from one hour at the station, and a list of sorted titles
    """
    if station.__len__() == 3:
        station = "C" + station

    one_station_url = urlroot + strdate + "/" + station + "/"

    one_station_html = get_html_string(one_station_url)

    one_station_xml_links = []
    one_station_soup = BeautifulSoup.BeautifulSoup(one_station_html)
    for tag in one_station_soup.findAll('a', href=True):
        if ".xml" and hour in tag['href']:
            file_name = tag['href'].encode('ascii','ignore')
            if file_name[11:13] == hour:
                one_station_xml_links.append(file_name)


    one_station_data_list, ordered_titles = parse_xml_links(one_station_url, one_station_xml_links, title_dict=title_dict, clean_dict=clean_dict, clean=clean)
    
    return one_station_data_list, ordered_titles

def get_fonts():
    """
    Here we set up a bunch of fonts for use in Excel formatting
    :returns: (dict) of font, border, and shading parameters to use with xlwt
    """
    borders = xlwt.Borders()
    borders.left = xlwt.Borders.THIN
    borders.right = xlwt.Borders.THIN
    borders.top = xlwt.Borders.THIN
    
    # Due to laziness this dictionary is called fonts, but it will also contain
    # shading and border information 
    fonts = {}
    fonts['font0'] = fonts['font1'] = fonts['font2'] = xlwt.Font()
    fonts['font0'].bold = fonts['font2'].bold = True
    fonts['font1'].name = fonts['font2'].name = 'Arial'
    fonts['font0'].name = 'Times New Roman'
    fonts['font0'].colour_index = 2
    fonts['font1'] = xlwt.Font()
    fonts['font1'].name = 'Arial'
    fonts['font2'] = xlwt.Font()
    fonts['font2'].name = 'Arial'
    fonts['font2'].bold = True
    fonts['style0'] = xlwt.XFStyle()
    fonts['style0'].border = borders
    fonts['style2'] = xlwt.XFStyle()
    fonts['style2'].border = borders
    fonts['style0'].font = fonts['font0']
    fonts['style2'].font = fonts['font2']
    fonts['style1'] = xlwt.easyxf('pattern: pattern solid;')
    fonts['style1'].border = borders
    fonts['style1'].font = fonts['font1']
    fonts['style1'].pattern.pattern_fore_colour = 1
    fonts['style2'] = xlwt.XFStyle()
    fonts['style2'].font = fonts['font2']
    fonts['stylea'] = xlwt.easyxf('pattern: pattern solid;')
    fonts['stylea'].border = borders
    fonts['stylea'].pattern.pattern_fore_colour = 40  #Blue
    fonts['styleb'] = xlwt.easyxf('pattern: pattern solid;')
    fonts['styleb'].border = borders
    fonts['styleb'].pattern.pattern_fore_colour = 55 #Grey
    fonts['stylec'] = xlwt.easyxf('pattern: pattern solid;')
    fonts['stylec'].border = borders
    fonts['stylec'].pattern.pattern_fore_colour = 2  #Red
    fonts['styled'] = xlwt.easyxf('pattern: pattern solid;')
    fonts['styled'].border = borders
    fonts['styled'].pattern.pattern_fore_colour = 5  #Yellow
    fonts['stylee'] = xlwt.easyxf('pattern: pattern solid;')
    fonts['stylee'].border = borders
    fonts['stylee'].pattern.pattern_fore_colour = 19 #BrownyGreen
    fonts['stylef'] = xlwt.easyxf('pattern: pattern solid;')
    fonts['stylef'].border = borders
    fonts['stylef'].pattern.pattern_fore_colour = 50  #Green
    
    # Determines style to use based on qualifiers
    fonts['qa_none'] = 'style1'
    fonts['-10'] = 'stylea'
    fonts['-1'] = 'styleb'
    fonts['0'] = 'stylec'
    fonts['10'] = 'styled'
    fonts['15'] = 'stylee'
    fonts['100'] = 'stylef'
    
    return fonts

def excel_out(data_list, titles_list, desired_filename, multi = False):
    """
    Outputs data to an Excel file
    :param data_list: a list of station information in 
        [{'fieldx_name':["datum","unit",(int) order,"quality"],'fieldx+1_name':[...]},{...},...] format
        where each dictionary in the list gets rendered as a row
    :param titles_list: a list of field title tuples ordered by priority in
        [("fieldx_name", [(int) priority, "unit"]), ("fieldx+1_name", [(int) priority, "unit"]),...] format
        where each tuple in the list is used to order the data in results_list and for the header data.
    :param desired_filename: (str) the name of the file to write the csv to
    :param multi: (optional bool) True if input is from multiple stations, False (default) otherwise
    :returns: (bool) True if successful, False otherwise
    """
    # Copy data_list so we can make changes
    data_list = copy.copy(data_list)
    # Add the titles to the end of the data_list
    data_list.append(titles_list)
    
    # Get the fonts so that we can qualify information by colour
    fonts_dict = get_fonts()
    
    # Open the desired_filename as an Excel file and write over existing
    excel_file = open(desired_filename, 'wb')
    
    # Set up workbook and worksheet (ws)
    work_book = xlwt.Workbook()
    ws = work_book.add_sheet('Sheet 1')
    
    # Print station ID and Name to top of Excel file
    stn_letter = data_list[0]['TC ID'][0]
    stn_name = data_list[0]['Station Name'][0]
    
    #Prints header to the Excel file
    if multi == False:
        ws.write(0,0,"Station Name", fonts_dict['style0'])
        ws.write(0,2,stn_name, fonts_dict['style1'])
        ws.write(0,4,"TC ID", fonts_dict['style0'])
        ws.write(0,5,stn_letter, fonts_dict['style1'])
    else:
        ws.write(0,0,"Multiple Stations", fonts_dict['style0'])
    
    # Prints qualifier information to Excel file
    ws.write(0,7,"Qualifiers", fonts_dict['style0'])
    ws.write(0,8,"Supressed", fonts_dict['stylea'])
    ws.write(0,9,"Missing", fonts_dict['styleb'])
    ws.write(0,10,"Error", fonts_dict['stylec'])
    ws.write(0,11,"Doubtful", fonts_dict['styled'])
    ws.write(0,12,"Suspect/Warning", fonts_dict['stylee'])
    ws.write(0,13,"Acceptable/Passed", fonts_dict['stylef'])
    
    #Gets the column to start at for each row
    starter_location= 0
    for name_item in data_list[-1]:
        starter_location+= 1
        if name_item[0] == "Station Name":
            if multi==True:
                starter_location-=2
            break
    #Prints column titles
    col_index = 2
    counter = starter_location
    ws.write(2,0,"Date & Time", fonts_dict['style0'])
    ws.write(2,1,"", fonts_dict['style0'])
    while counter < data_list[-1].__len__():
        col_title = str(data_list[-1][counter][0])
        col_units = str(data_list[-1][counter][1][1])
        ws.write(2,col_index,col_title+" ("+col_units+")",fonts_dict['style0'])
        counter+=1
        col_index+=1
        
    # Starting on this row we write the data to the file
    row_index = 3
    for hour_line in range(0,data_list.__len__()-1):
        col_index = 2
        time = str(data_list[hour_line]['date_tm'][0][:16].replace('T',' '))+"Z"
        ws.write(row_index,0,time,fonts_dict['style1'])
        ws.write(row_index,1,"",fonts_dict['style1'])
        counter = starter_location
        while counter < data_list[-1].__len__():
            try:
                key = str(data_list[-1][counter][0])
                datum = str(data_list[hour_line][key][0])
                qual = str(data_list[hour_line][key][3])
                ws.write(row_index,col_index,datum,fonts_dict[fonts_dict[qual]])
            except:
                pass
            counter+=1
            col_index+=1
        row_index+=1
    
    try:
        work_book.save(excel_file)
        return True
    except:
        return False

def csv_out(results_list, finial_title, filename, date):
    """
    Outputs data to a CSV file
    :param results_list: a list of station information in 
        [{'fieldx_name':["datum","unit",(int) order,"quality"],'fieldx+1_name':[...]},{...},...] format
        where each dictionary in the list gets rendered as a row
    :param ordered_titles: a list of field title tuples ordered by priority in
        [("fieldx_name", [(int) priority, "unit"]), ("fieldx+1_name", [(int) priority, "unit"]),...] format
        where each tuple in the list is used to order the data in results_list and for the header data.
    :param clean_dict: a dict that used to store the assigned index of given element
    :param finial_title: a list contain the all the titles that are ready to be printed to output file
    :length: a int is half of the total length of finial_title
    :param filename: (str) the name of the file to write the csv to
    :returns: (bool) True if successful, False otherwise
    """
    try:
                   
        # Write the header and data to the csv file
        x = 0
	if not os.path.exists("/apps/data/outgoing/eccc/cmc/dmsec/swob-consolidated/" + str(date)):
            os.makedirs("/apps/data/outgoing/eccc/cmc/dmsec/swob-consolidated/" + str(date))
 
	if os.path.exists("/apps/data/outgoing/eccc/cmc/dmsec/swob-consolidated/" + str(date) + "/" + str(filename) + ".csv"):
            with open("/apps/data/outgoing/eccc/cmc/dmsec/swob-consolidated/" + str(date) + "/" + str(filename) + ".csv", "a") as f:
		writer = csv.writer(f)
                while x < len(results_list):
		    writer.writerow(results_list[x])
		    x = x + 1
        else:
            with open("/apps/data/outgoing/eccc/cmc/dmsec/swob-consolidated/" + str(date) + "/" + str(filename) + ".csv", "wb") as f:
                writer = csv.writer(f)
                writer.writerow(finial_title)
		while x < len(results_list):
                    writer.writerow(results_list[x])
		    x = x + 1
	x = 0
        if not os.path.exists("/apps/data/consolidated-swob/" + "Consolidated_Monthly_File.csv"):
            with open("/apps/data/consolidated-swob/" + "Consolidated_Monthly_File.csv","w") as f:
                writer = csv.writer(f)
                writer.writerow(finial_title)
                while x < len(results_list):
                    writer.writerow(results_list[x])
                    x = x + 1
        else:
            with open("/apps/data/consolidated-swob/" + "Consolidated_Monthly_File.csv","a") as f:
                writer = csv.writer(f)
                while x < len(results_list):
                    writer.writerow(results_list[x])
                    x = x + 1

        # We were successful
        return True
    except Exception, err:
        #print str(err)
	logging.error(str(err))
        # An error occurred
        return False


def sort_title(clean_dict, title):
    """
    :param clean_dict: a dict contains the readable and original element name, and a number represent the index of this element in a output list
    :param title: a list contain all keys of clean_dict
    return: list of finial title, and half of the length of the list
    """
    finial_title = []
    
    for element in title:
	#print clean_dict.get(element)[1]
	finial_title.insert(clean_dict.get(element)[1],clean_dict.get(element)[0])
	finial_title.insert(clean_dict.get(element)[1] + 1, "QA Summary")
    
    return finial_title, len(title)

def order_row(row, ordered_titles, clean_dict, length):
    """
    Orders an individual row so that it follows the field order of ordered_titles
    :param row: results_list
    :param ordered_titles: a list of field title tuples ordered by priority in
        [("fieldx_name", [(int) priority, "unit"]), ("fieldx+1_name", [(int) priority, "unit"]),...] format
        where each tuple in the list is used to order the data in results_list and for the header data.
    :param clean_dict: dict used to match readable and original name
    :param length: a int used to determine the length of output list
    :returns: (list) a row as a list with just the data values as columns.  QA included
    """
    try:

	final_ordered_row = []
	x = 0
	while x < len(row):      
	    ordered_row = [""] * length * 2 
	    for name in ordered_titles:
	        if  clean_dict.get(name[0],[""]) != [""]:                
                    if row[x].get(name[0],[""]) != [""]:
		        ordered_row[clean_dict.get(name[0])[1]] = str(row[x].get(name[0])[0])
		        ordered_row[clean_dict.get(name[0])[1] + 1] = str(row[x].get(name[0])[3])    
	    
	    final_ordered_row.append(ordered_row)
	    
	    x = x + 1
	
	return final_ordered_row
    except Exception, err:
	logging.error(str(err))
        print str(err)
        print clean_dict.get(name[0])[1]
        return ordered_row

def sort_by_station_name(date):
    Pv = ["BC","AB","SK","MB","ON","QC","NB","NS","NL","PE","YT","NU","NT"]
    outputdate = date.strftime("%Y-%m-%d-")
    Month = date.strftime("%Y-%B")
    strdate = date.strftime("%Y%m%d")
    one_day = datetime.timedelta(days=1)
    past_date_str = int((date - 30*one_day).strftime("%Y%m%d"))
    print past_date_str
    for p in Pv:
        unSortedList = []
	SortedList = []
	with open("/apps/data/outgoing/eccc/cmc/dmsec/swob-consolidated/" + str(strdate) + "/" + str(outputdate) + str(p) + ".csv", "r") as f:
	    read = csv.reader(f, delimiter = ",")
	    title = read.next()
	    for row in read:
	        if "".join(row) == "":	
		    continue
	        unSortedList.append(row)
            #print unSortedList
	    SortedList = sorted(unSortedList, key=itemgetter(2,0))
	    
	with open("/apps/data/outgoing/eccc/cmc/dmsec/swob-consolidated/" + str(strdate) + "/" + str(outputdate) + str(p) + ".csv", "w") as f:
	    writer = csv.writer(f)
	    writer.writerow(title)
	    writer.writerows(SortedList)
	
	
    with open("/apps/data/consolidated-swob/" + "Consolidated_Monthly_File.csv","r") as f:
        data_read = csv.reader(f, delimiter = ",")
        title = data_read.next()
        Data_List = []
        for row in data_read:
            if "".join(row) == "":
                continue
            elif  int(row[0][0:10].replace('-','')) < past_date_str:
                continue
            else:
                Data_List.append(row)

    with open("/apps/data/consolidated-swob/" + "Consolidated_Monthly_File.csv","w") as f:
        writer = csv.writer(f)
        writer.writerow(title)
        x = 0
        while x < len(Data_List):
            writer.writerow(Data_List[x])
            x = x + 1

"""
Main Class
"""
if __name__ == "__main__":
    
    PARSER = \
        argparse.ArgumentParser(description = 'Swob XML to CSV.')

    PARSER.add_argument(
        '--mode',
        help = 'Execution mode',
        required = True,
        choices = (
            'Hourly',
            'Initial',
            'Specified'
        )
    )

    PARSER.add_argument(
        '--StartDate',
        help = 'Choose Starting Date if using Specified Execition Mode. Format: YYYYMMDD',
        required = False
    )

    PARSER.add_argument(
        '--EndDate',
        help = 'Choose Finishing Date if using Specified Execition Mode. Format: YYYYMMDD',
        required = False
    )



    ARGS = PARSER.parse_args()
    
    #Mapping station to province list
    with open("mapfile.csv","r") as f:
        ID = []
        Province = []
        f.readline()
        WrongID = [] 
        while True:
            line = f.readline()
            if line == '\n':
                break;
            parts = line.split(",")
            if parts[3] == '\n':
                continue
            ID.append(parts[3])
            Province.append(parts[1])

    #get today's date and time
    td = datetime.datetime.utcnow()
    one_day = datetime.timedelta(days=1)
    strdate = td.strftime("%Y%m%d")
    
    """Check for running for condition, if flag.txt does not exit, progrom will perform a initial run 
    to consolidate data from the past 30 days, then create the flag.txt file.
    If flag.txt exist, program will directly enter hourly mode to consolidate data every hour"""
    if ARGS.mode == 'Hourly':
        print ("Hourly mode\n") 
	logging.info(datetime.datetime.utcnow().strftime("%Y%m%d   %H:%M")+" Hourly process started\n")
	
        time_now = datetime.datetime.utcnow()
        hr = time_now.strftime("%H")
        all_stations = get_stations_list(urlroot,strdate)
        clean_dict, clean, raw_title = clean_incoming()
        finial_title, length = sort_title(clean_dict, raw_title)
        hour = int(hr)
        if hour == 00:
            hour = 23
        else:
            hour = hour - 1 

        for station in all_stations:
            try:
                ind = ID.index(station + "\n")
                Pro = Province[ind]
                result_list, ordered_titles = parse_station_hourly(urlroot,strdate,str(hour),station,clean_dict=clean_dict,clean=clean)
		ordered_results_list = order_row(result_list, ordered_titles, clean_dict, length)
		outputdate = td.strftime("%Y-%m-%d")
                csv_out(ordered_results_list, finial_title, outputdate+"-"+Pro, strdate)
            except Exception, err:
		print str(err)
		logging.error(str(err))
                WrongID.append(station)
                continue
        sort_by_station_name(time_now)
	logging.info(datetime.datetime.utcnow().strftime("%Y%m%d   %H:%M")+" Hourly process finished\n")
        logging.info("These stations is not on station mapping list: " + " ".join(WrongID) + "\n")
        
        
    elif ARGS.mode == 'Initial':   
        
	days = 30
        time_now = datetime.datetime.utcnow()
        logging.info(td.strftime("%Y%m%d   %H:%M")+" initial process starts\n")
        logging.info("\n")
        clean_dict, clean, raw_title = clean_incoming()
        finial_title, length = sort_title(clean_dict, raw_title)
        while days > 0:
            print days
            date  = td - days*one_day
            strdate = date.strftime("%Y%m%d")
            all_stations = get_stations_list(urlroot,strdate)
            for station in all_stations:
                try:
                    ind = ID.index(station + "\n") 
                    Pro = Province[ind]
                    result_list, ordered_titles = parse_station(urlroot,strdate,station,clean_dict=clean_dict,clean=clean)
		    ordered_results_list = order_row(result_list, ordered_titles, clean_dict, length) 
		    outputdate = date.strftime("%Y-%m-%d")
                    csv_out(ordered_results_list, finial_title, outputdate+"-"+Pro, strdate)
                except Exception, err:
		    print str(err)
		    logging.error(str(err))
                    WrongID.append(station)
                    continue
            days = days - 1
            sort_by_station_name(date)    
        logging.info(datetime.datetime.utcnow().strftime("%Y%m%d   %H:%M") + " initial process ended\n")
        logging.info("These stations is not on station mapping list: " + " ".join(WrongID) + "\n")
       
       
    elif ARGS.mode == 'Specified':
	
	days = 0
        start_time = ARGS.StartDate
	end_time = ARGS.EndDate
        logging.info(td.strftime("%Y%m%d   %H:%M")+" specified process starts, from " + start_time + " to " + end_time + "\n")
        logging.info("\n")
        clean_dict, clean, raw_title = clean_incoming()
        finial_title, length = sort_title(clean_dict, raw_title)

        while days <= (int(end_time) - int(start_time)):
            
            date  = str(int(start_time) + days)
            all_stations = get_stations_list(urlroot,str(strdate))
            for station in all_stations:
                try:
                    ind = ID.index(str(station) + "\n")
		    Pro = Province[ind]
                    results_list, ordered_titles = parse_station(urlroot,str(date),station,clean_dict=clean_dict,clean=clean)
		    ordered_results_list = order_row(results_list, ordered_titles, clean_dict, length)
                    outputdate = date[0:4]+'-'+date[4:6]+'-'+date[6:]
                    csv_out(ordered_results_list, finial_title, outputdate+'-'+Pro, date)
    
                except Exception, err:
		    print str(err)
		    logging.error(str(err))
                    WrongID.append(station)
                    continue
            days = days + 1

	logging.info(datetime.datetime.utcnow().strftime("%Y%m%d   %H:%M") + " Specified process ended\n")
        logging.info("These stations is not on station mapping list: " + " ".join(WrongID) + "\n")
        
    
             
    
    
