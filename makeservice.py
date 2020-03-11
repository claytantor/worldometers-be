import argparse
import pystache 
import sys

def loadTemplate(templateFile):
    cfg = None

    data = ""
    with open(templateFile, 'r') as file:
        data = file.read()

    return data

def main(argv):

    # Read in command-line parameters
    parser = argparse.ArgumentParser()

    parser.add_argument("-d", "--dir", action="store", required=True, dest="dir", help="the install dir")
    parser.add_argument("-t", "--template", action="store", required=True, dest="template", help="the service template")

    args = parser.parse_args()
    print(pystache.render(loadTemplate(args.template), args))
    
    
if __name__ == "__main__":
    main(sys.argv[1:])