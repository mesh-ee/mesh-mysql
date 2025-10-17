Reads packets from a node over TCP and inserts them to a MySQL server.


# Just some notes
-128 snr in traceroute means invalid/unkown. 4294967295 long_id means ^all so a broadcast CQ. If a broadcast happens it is still writen in the packet to stay aligned both of the snrTowards and route need to be the same length and thats why the -128 is there.
