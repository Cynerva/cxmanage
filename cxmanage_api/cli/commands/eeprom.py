"""Calxeda: eeprom.py """

# Copyright (c) 2012, Calxeda Inc.
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
# * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
# * Neither the name of Calxeda Inc. nor the names of its contributors
# may be used to endorse or promote products derived from this software
# without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDERS OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS
# OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
# TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF
# THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
# DAMAGE.

from cxmanage_api.cli import get_nodes, get_tftp, run_command, prompt_yes

def eepromupdate_command(args):
    """Updates the EEPROM's on a cluster or host"""
    def validate_config():
        """Makes sure the system type is applicable to EEPROM updates"""
        for node in  nodes:
            if('Dual Node' not in node.get_versions().hardware_version):
                print 'ERROR: eepromupdate is only valid on TerraNova systems'
                return True

        return False

    def validate_images():
        """Makes sure all the necessary images have been provided"""
        if(args.eeprom_location == 'node'):
            for node in nodes:
                node_hw_ver = node.get_versions().hardware_version
                if('Uplink' in node_hw_ver):
                    image = 'dual_uplink_node_%s' % (node.node_id % 4)
                else:
                    image = 'dual_node_%s' % (node.node_id % 4)
                if(not [img for img in args.images if image in img]):
                    print 'ERROR: no valid image for node %s' % node.node_id
                    return True

        else:
            image = args.images[0]
            if('tn_storage.single_slot' not in image):
                print 'ERROR: %s is an invalid image for slot EEPROM' % image
                return True

        return False

    def do_update():
        """Updates the EEPROM images"""
        if(args.eeprom_location == 'node'):
            for node in nodes:
                node_hw_ver = node.get_versions().hardware_version
                if('Uplink' in node_hw_ver):
                    needed_image = 'dual_uplink_node_%s' % (node.node_id % 4)
                else:
                    needed_image = 'dual_node_%s' % (node.node_id % 4)
                image = [img for img in args.images if needed_image in img][0]
                print 'Updating node EEPROM on node %s' % node.node_id
                if(args.verbose):
                    print '    %s' % image
                try:
                    node.update_node_eeprom(image)
                except Exception as err:
                    print 'ERROR: %s' % str(err)
                    return True

            print ''  # for readability
        else:
            image = args.images[0]
            # First node in every slot gets the slot image
            slot_nodes = [node for node in nodes if node.node_id % 4 == 0]
            _, errors = run_command(
                args, slot_nodes, "update_slot_eeprom", image
            )
            if(errors):
                print 'ERROR: EEPROM update failed'
                return True

        return False

    if not args.all_nodes:
        if args.force:
            print(
                'WARNING: Updating EEPROM without --all-nodes' +
                ' is dangerous.'
            )
        else:
            if not prompt_yes(
                'WARNING: Updating EEPROM without ' +
                '--all-nodes is dangerous. Continue?'
                ):
                return 1

    tftp = get_tftp(args)
    nodes = get_nodes(args, tftp, verify_prompt=True)

    errors = validate_config()

    if(not errors):
        errors = validate_images()

    if(not errors):
        errors = do_update()

    if not args.quiet and not errors:
        print "Command completed successfully."
        print "A power cycle is required for the update to take effect.\n"

    return errors


