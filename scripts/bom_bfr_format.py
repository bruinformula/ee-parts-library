#
# Bruin Formula Racing python script to generate a BOM from a KiCad generic netlist
#

"""
    @package
    Generates a CSV format component BOM sheet for the current schematic.
    Output: one BOM CSV file
    "Component", "Qty per Unit", "Units", "Cost/Unit", "Link", "Part Number"

    Also generates a CSV format order BOM for products from each supplier X "X P/N",
    "X Link", and "Order From" fields. Note that "Order From" must be set exactly to "X".
    Output: one CSV file per supplier
    "Component", "Order Qty", "Part Number", "Link".

    Note that, for this BOM generator to work properly, fields must be added to the
    schematic symbols in the project. This step can be expedited by populating these
    fields in the component library. The fields are (where X is a supplier specified in
    the "Order From" field):
    "Pretty Name", "Qty/Unit", "Cost/Unit", "Order From", "X P/N", and "X Link"

    To create a BOM for multiple boards, specify the final command line argument as some
    number greater than 1 (specifically, the number of boards).

    Command line:
    Example: python "pathToFile/bom_bfr_format.py" "%I" "%O.csv" 1
"""

# === BEGIN utility behavior for I/O from built-in KiCad BOM scripts ===

from __future__ import print_function

# Import the KiCad python helper module and the csv formatter
import kicad_netlist_reader
import kicad_utils
import csv
import sys

# A helper function to filter/convert a string read in netlist
#currently: do nothing
def fromNetlistText( aText ):
    return aText

def myEqu(self, other):
    """myEqu is a more advanced equivalence function for components which is
    used by component grouping. Normal operation is to group components based
    on their value and footprint.

    In this example of a custom equivalency operator we compare the
    value, the part name and the footprint.
    """
    result = True
    if self.getValue() != other.getValue():
        result = False
    elif self.getPartName() != other.getPartName():
        result = False
    elif self.getFootprint() != other.getFootprint():
        result = False
    elif self.getDNP() != other.getDNP():
        result = False

    return result

# Override the component equivalence operator - it is important to do this
# before loading the netlist, otherwise all components will have the original
# equivalency operator.
kicad_netlist_reader.comp.__eq__ = myEqu

if len(sys.argv) != 4:
    print("Usage ", __file__, "<generic_netlist.xml> <output.csv> <QTY>", file=sys.stderr)
    sys.exit(1)

# Generate an instance of a generic netlist, and load the netlist tree from
# the command line option. If the file doesn't exist, execution will stop
net = kicad_netlist_reader.netlist(sys.argv[1])

# subset the components to those wanted in the BOM, controlled
# by <configure> block in kicad_netlist_reader.py
components = net.getInterestingComponents(excludeBOM=True)
compfields = net.gatherComponentFieldUnion(components)
partfields = net.gatherLibPartFieldUnion()
# remove Reference, Value, Datasheet, and Footprint, they will come from 'columns' below
partfields -= set( ['Reference', 'Value', 'Datasheet', 'Footprint'] )
columnset = compfields | partfields     # union
# prepend an initial 'hard coded' list and put the enchillada into list 'columns'
hardcoded_columns = ['Item', 'Qty', 'Reference(s)', 'Value', 'LibPart', 'Footprint', 'Datasheet', 'DNP']
columns = hardcoded_columns + sorted(list(columnset))

# override csv.writer's writerow() to support encoding conversion (initial encoding is utf8):
def writerow( acsvwriter, columns ):
    utf8row = []
    for col in columns:
        utf8row.append( fromNetlistText( str(col) ) )
    acsvwriter.writerow( utf8row )

# Get all of the components in groups of matching parts + values
# (see kicad_netlist_reader.py)
grouped = net.groupComponents(components)

# === END utility behavior for I/O from built-in KiCad BOM scripts ===

try:
    bfr_bom_file = kicad_utils.open_file_writeUTF8(sys.argv[2][:-4]+"_BOM.csv", 'w')
except IOError:
    e = "Can't open output file for writing: " + sys.argv[2]
    print( __file__, ":", e, sys.stderr )
    bfr_bom_file = sys.stdout

# Create a new csv writer object to use as the output formatter
out = csv.writer( bfr_bom_file, lineterminator='\n', delimiter=',', quotechar='\"', quoting=csv.QUOTE_ALL )

suppliers_in_use = set()

writerow( out, ["Component", "Qty per Unit", "Units", "Cost/Unit", "Link", "Part Number"] )
# Output component information organized by group, aka as collated:
for group in grouped:
    row = []
    row.append(net.getGroupField(group, "Pretty Name"))
    try:
        per = int(net.getGroupField(group, "Qty/Unit"))
    except ValueError:
        per = 1
    row.append(per)
    row.append((len(group) * int(sys.argv[3])) // per + (1 if len(group)%per else 0)) # Units
    row.append(net.getGroupField(group, "Cost/Unit"))
    src = net.getGroupField(group, "Order From")
    if (src != ""):
        suppliers_in_use.add(src)
        row.append(net.getGroupField(group, src + " Link"))
        row.append(net.getGroupField(group, src + " P/N"))
    writerow(out, row)

bfr_bom_file.close()

for supplier in suppliers_in_use:
    try:
        order_bom_file = kicad_utils.open_file_writeUTF8(sys.argv[2][:-4]+"_"+supplier+"-order.csv", 'w')
    except IOError:
        e = "Can't open output file for writing: " + sys.argv[2]
        print( __file__, ":", e, sys.stderr )
        order_bom_file = sys.stdout
    out = csv.writer( order_bom_file, lineterminator='\n', delimiter=',', quotechar='\"', quoting=csv.QUOTE_ALL )
    writerow( out, ["Component", "Order Qty", "Part Number", "Link"] )
    for group in grouped:
        if (net.getGroupField(group, "Order From") == supplier):
            row = []
            row.append(net.getGroupField(group, "Pretty Name"))
            try:
                per = int(net.getGroupField(group, "Qty/Unit"))
            except ValueError:
                per = 1
            row.append((len(group) * int(sys.argv[3])) // per + (1 if len(group)%per else 0)) # Units
            row.append(net.getGroupField(group, supplier + " P/N"))
            row.append(net.getGroupField(group, supplier + " Link"))
            writerow(out, row)
    order_bom_file.close()
