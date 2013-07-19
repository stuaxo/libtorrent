import glob
import os
import sys

paths = ['include/libtorrent/*.hpp', 'include/libtorrent/kademlia/*.hpp', 'include/libtorrent/extensions/*.hpp']

files = []

for p in paths:
	files.extend(glob.glob(os.path.join('..', p)))

functions = []
classes = []
enums = []

# maps names -> URL
symbols = {}

verbose = '--verbose' in sys.argv
dump = '--dump' in sys.argv
internal = '--internal' in sys.argv

category_mapping = {
	'error_code.hpp': 'Error Codes',
	'file.hpp': 'File',
	'storage.hpp': 'Storage',
	'storage_defs.hpp': 'Storage',
	'file_storage.hpp': 'Storage',
	'file_pool.hpp': 'Storage',
	'extensions.hpp': 'Plugins',
	'ut_metadata.hpp': 'Plugins',
	'ut_pex.hpp': 'Plugins',
	'ut_trackers.hpp': 'Plugins',
	'metadata_transfer.hpp': 'Plugins',
	'smart_ban.hpp': 'Plugins',
	'lt_trackers.hpp': 'Plugins',
	'create_torrent.hpp': 'Create Torrents',
	'alert.hpp': 'Alerts',
	'alert_types.hpp': 'Alerts',
	'bencode.hpp': 'Bencoding',
	'lazy_entry.hpp': 'Bencoding',
	'entry.hpp': 'Bencoding',
	'time.hpp': 'Time',
	'ptime.hpp': 'Time',
	'escape_string.hpp': 'String',
	'string_util.hpp': 'String',
	'utf8.hpp': 'String',
	'enum_net.hpp': 'Network',
	'broadcast_socket.hpp': 'Network',
	'socket.hpp': 'Network',
	'socket_io.hpp': 'Network',
	'rss.hpp': 'RSS',
	'bitfield.hpp': 'Utility',
	'peer_id.hpp': 'Utility',
	'identify_client.hpp': 'Utility',
	'thread.hpp': 'Utility',
}

def categorize_symbol(name, filename):
	f = os.path.split(filename)[1]
	if f in category_mapping:
		return category_mapping[f]

	if name.endswith('_category') \
		or name.endswith('_error_code') \
		or name.endswith('error_code_enum'):
		return 'Error Codes'

	return 'Core'

def html_sanitize(s):
	ret = ''
	for i in s:
		if i == '<': ret += '&lt;'
		elif i == '>': ret += '&gt;'
		elif i == '&': ret += '&amp;'
		else: ret += i
	return ret

def looks_like_variable(line):
	line = line.strip()
	if not line.endswith(';'): return False
	if not ' ' in line and not '\t' in line: return False
	if line.startswith('friend '): return False
	if line.startswith('enum '): return False
	if line.startswith(','): return False
	if line.startswith(':'): return False
	return True

def looks_like_function(line):
	if line.startswith(','): return False
	if line.startswith(':'): return False
	return '(' in line;

def parse_function(lno, lines, filename):
	current_fun = {}

	start_paren = 0
	end_paren = 0
	signature = ''

	while lno < len(lines):
		l = lines[lno].strip()
		lno += 1
		if l.startswith('//'): continue

		start_paren += l.count('(')
		end_paren += l.count(')')

		sig_line = l.replace('TORRENT_EXPORT ', '').strip()
		if signature != '': sig_line = '\n   ' + sig_line
		signature += sig_line
		if verbose: print 'fun     %s' % l

		if start_paren > 0 and start_paren == end_paren:
			if signature[-1] != ';':
				# we also need to consume the function body
				start_paren = 0
				end_paren = 0
				for i in range(len(signature)):
					if signature[i] == '(': start_paren += 1
					elif signature[i] == ')': end_paren += 1

					if start_paren > 0 and start_paren == end_paren:
						for k in range(i, len(signature)):
							if signature[k] == ':' or signature[k] == '{':
								signature = signature[0:k].strip()
								break
						break

				lno = consume_block(lno - 1, lines)
				signature += ';'
			return [{ 'file': filename[11:], 'signature': signature, 'name': signature.split('(')[0].split(' ')[-1].strip()}, lno]
	if len(signature) > 0:
		print '\x1b[31mFAILED TO PARSE FUNCTION\x1b[0m %s\nline: %d\nfile: %s' % (signature, lno, filename)
	return [None, lno]

def parse_class(lno, lines, filename):
	start_brace = 0
	end_brace = 0

	name = ''
	funs = []
	fields = []
	enums = []
	state = 'public'
	context = ''
	class_type = 'struct'

	while lno < len(lines):
		l = lines[lno].strip()
		name += lines[lno].replace('TORRENT_EXPORT ', '').split('{')[0].strip()
		if '{' in l: break
		if verbose: print 'class  %s' % l
		lno += 1

	if name.startswith('class'):
		state = 'private'
		class_type = 'class'

	while lno < len(lines):
		l = lines[lno].strip()
		lno += 1

		if l.startswith('/*'):
			lno = consume_comment(lno - 1, lines)
			continue

		if l.startswith('#'):
			lno = consume_ifdef(lno - 1, lines)
			continue

		if 'TORRENT_DEFINE_ALERT' in l:
			if verbose: print 'xx    %s' % l
			continue
		if 'TORRENT_DEPRECATED' in l:
			if verbose: print 'xx    %s' % l
			continue

		if l.startswith('//'):
			if verbose: print 'desc  %s' % l
			l = l.split('//')[1]
			context += l + '\n'
			continue

		start_brace += l.count('{')
		end_brace += l.count('}')

		if l == 'private:': state = 'private'
		elif l == 'protected:': state = 'protected'
		elif l == 'public:': state = 'public'

		if start_brace > 0 and start_brace == end_brace:
			return [{ 'file': filename[11:], 'enums': enums, 'fields':fields, 'type': class_type, 'name': name.split(':')[0].replace('class ', '').replace('struct ', '').strip(), 'decl': name, 'fun': funs}, lno]

		if state != 'public' and not internal:
			if verbose: print 'private %s' % l
			continue

		if start_brace - end_brace > 1:
			if verbose: print 'scope   %s' % l
			continue;

		if looks_like_function(l):
			current_fun, lno = parse_function(lno - 1, lines, filename)
			if current_fun != None:
				current_fun['desc'] = context
				funs.append(current_fun)
			context = ''
			continue

		if looks_like_variable(l):
			fields.append({ 'signature': l, 'name': l.split(' ')[-1].split(':')[0].split(';')[0], 'desc': context})
			context = ''
			continue

		if l.startswith('enum '):
			enum, lno = parse_enum(lno - 1, lines, filename)
			if enum != None:
				enum['desc'] = context
				enums.append(enum)
			context = ''
			continue

		context = ''
		if verbose: print '??      %s' % l
   
	if len(name) > 0:
		print '\x1b[31mFAILED TO PARSE CLASS\x1b[0m %s\nfile: %s:%d' % (name, filename, lno)
	return [None, lno]

def parse_enum(lno, lines, filename):
	start_brace = 0
	end_brace = 0

	l = lines[lno].strip()
	name = l.replace('enum ', '').split('{')[0].strip()
	if len(name) == 0:
		print 'WARNING: anonymous enum at: %s:%d' % (filename, lno)
		lno = consume_block(lno - 1, lines)
		return [None, lno]

	values = []
	context = ''
	if not '{' in l:
		if verbose: print 'enum  %s' % lines[lno]
		lno += 1

	while lno < len(lines):
		l = lines[lno].strip()
		lno += 1

		if l.startswith('//'):
			if verbose: print 'desc  %s' % l
			l = l.split('//')[1]
			context += l + '\n'
			continue

		if l.startswith('#'):
			lno = consume_ifdef(lno - 1, lines)
			continue

		start_brace += l.count('{')
		end_brace += l.count('}')

		if '{' in l: 
			l = l.split('{')[1]
		l = l.split('}')[0]

		if len(l):
			if verbose: print 'enum  %s' % lines[lno-1]
			for v in l.split(','):
				if v == '': continue
				values.append({'name': v.strip(), 'desc': context})
				context = ''
		else:
			if verbose: print '??    %s' % lines[lno-1]

		if start_brace > 0 and start_brace == end_brace:
			return [{'file': filename, 'name': name, 'values': values}, lno]

	if len(name) > 0:
		print '\x1b[31mFAILED TO PARSE ENUM\x1b[0m %s\nline: %d\nfile: %s' % (name, lno, filename)
	return [None, lno]

def consume_block(lno, lines):
	start_brace = 0
	end_brace = 0

	while lno < len(lines):
		l = lines[lno].strip()
		if verbose: print 'xx    %s' % l
		lno += 1

		start_brace += l.count('{')
		end_brace += l.count('}')

		if start_brace > 0 and start_brace == end_brace:
			break
	return lno

def consume_comment(lno, lines):
	while lno < len(lines):
		l = lines[lno].strip()
		if verbose: print 'xx    %s' % l
		lno += 1
		if '*/' in l: break

	return lno

def consume_ifdef(lno, lines):
	l = lines[lno].strip()
	lno += 1

	start_if = 1
	end_if = 0

	if verbose: print 'prep  %s' % l

	if l == '#ifndef TORRENT_NO_DEPRECATE' or \
		l == '#ifdef TORRENT_DEBUG' or \
		(l.startswith('#if') and 'defined TORRENT_DEBUG' in l):
		while lno < len(lines):
			l = lines[lno].strip()
			lno += 1
			if verbose: print 'prep  %s' % l
			if l.startswith('#endif'): end_if += 1
			if l.startswith('#if'): start_if += 1
			if l == '#else' and start_if - end_if == 1: break
			if start_if - end_if == 0: break
		return lno

	return lno

for filename in files:
	h = open(filename)
	lines = h.read().split('\n')

	if verbose: print '\n=== %s ===\n' % filename

	lno = 0
	while lno < len(lines):
		l = lines[lno].strip()
		lno += 1

		if l.startswith('//'):
			if verbose: print 'desc  %s' % l
			l = l.split('//')[1]
			context += l + '\n'
			continue

		if l.startswith('/*'):
			lno = consume_comment(lno - 1, lines)
			continue

		if l.startswith('#'):
			lno = consume_ifdef(lno - 1, lines)
			continue

		if 'TORRENT_CFG' in l:
			if verbose: print 'xx    %s' % l
			continue
		if 'TORRENT_DEPRECATED' in l:
			if verbose: print 'xx    %s' % l
			continue

		if 'TORRENT_EXPORT ' in l:
			if 'class ' in l or 'struct ' in l:
				current_class, lno = parse_class(lno -1, lines, filename)
				if current_class != None:
					current_class['desc'] = context
					classes.append(current_class)
				context = ''
				continue

			if looks_like_function(l):
				current_fun, lno = parse_function(lno - 1, lines, filename)
				if current_fun != None:
					current_fun['desc'] = context
					functions.append(current_fun)
				context = ''
				continue

		if ('class ' in l or 'struct ' in l) and not ';' in l:
			lno = consume_block(lno - 1, lines)
			context = ''
			continue

		if l.startswith('enum '):
			current_enum, lno = parse_enum(lno - 1, lines, filename)
			if current_enum != None:
				current_enum['desc'] = context
				enums.append(current_enum)
			context = ''
			continue

		if verbose: print '??    %s' % l

		context = ''
	h.close()

if dump:

	if verbose: print '\n===============================\n'

	for c in classes:
		print '\x1b[4m%s\x1b[0m %s\n{' % (c['type'], c['name'])
		for f in c['fun']:
			print '   %s' % f['signature'].replace('\n', '\n   ')

		if len(c['fun']) > 0 and len(c['fields']) > 0: print ''

		for f in c['fields']:
			print '   %s' % f['signature']

		if len(c['fields']) > 0 and len(c['enums']) > 0: print ''

		for e in c['enums']:
			print '   \x1b[4menum\x1b[0m %s\n   {' % e['name']
			for v in e['values']:
				print '      %s' % v['name']
			print '   };'
		print '};\n'

	for f in functions:
		print '%s' % f['signature']

	for e in enums:
		print '\x1b[4menum\x1b[0m %s\n{' % e['name']
		for v in e['values']:
			print '   %s' % v['name']
		print '};'

categories = {}

for c in classes:
	cat = categorize_symbol(c['name'], c['file'])
	if not cat in categories:
		categories[cat] = { 'classes': [], 'functions': [], 'enums': [], 'filename': 'reference-%s.html' % cat.replace(' ', '_')}
	categories[cat]['classes'].append(c)
	symbols[c['name']] = categories[cat]['filename'] + '#' + html_sanitize(c['name'])

for f in functions:
	cat = categorize_symbol(f['name'], f['file'])
	if not cat in categories:
		categories[cat] = { 'classes': [], 'functions': [], 'enums': [], 'filename': 'reference-%s.html' % cat.replace(' ', '_')}
	categories[cat]['functions'].append(f)
	symbols[f['name']] = categories[cat]['filename'] + '#' + html_sanitize(f['name'])

for e in enums:
	cat = categorize_symbol(e['name'], e['file'])
	if not cat in categories:
		categories[cat] = { 'classes': [], 'functions': [], 'enums': [], 'filename': 'reference-%s.html' % cat.replace(' ', '_')}
	categories[cat]['enums'].append(e)
	symbols[e['name']] = categories[cat]['filename'] + '#' + html_sanitize(e['name'])

out = open('reference.html', 'w+')
out.write('''<html><head>
<link rel="stylesheet" type="text/css" href="../../css/base.css" />
<link rel="stylesheet" type="text/css" href="../../css/rst.css" />
<link rel="stylesheet" href="style.css" type="text/css" />
</head><body>
<h1>libtorrent reference documentation</h1>
<div style="column-count: 5; -webkit-column-count: 5; -moz-column-count: 5">''')

def print_declared_in(out, o):
	out.write('<p>Declared in <a href="../include/%s"><tt class="docutils-literal">"%s"</tt></a></p>' % (o['file'], html_sanitize(o['file'])))

def print_link(out, name):
	our.write('<a href="%s">%s</a>' % (symbols[name], name))

for cat in categories:
	print >>out, '<h2>%s</h2>' % cat
	category_filename = categories[cat]['filename']
	for c in categories[cat]['classes']:
		print >>out, '<a href="%s#%s">%s %s</a><br/>' % (category_filename, html_sanitize(c['name']), html_sanitize(c['type']), html_sanitize(c['name']))
	for f in categories[cat]['functions']:
		print >>out, '<a href="%s#%s">%s()</a><br/>' % (category_filename, html_sanitize(f['name']), html_sanitize(f['name']))
	for e in categories[cat]['enums']:
		print >>out, '<a href="%s#%s">enum %s</a><br/>' % (category_filename, html_sanitize(e['name']), html_sanitize(e['name']))

out.write('</div></body></html>')
out.close()

for cat in categories:
	out = open(categories[cat]['filename'], 'w+')

	classes = categories[cat]['classes']
	functions = categories[cat]['functions']
	enums = categories[cat]['enums']

	out.write('''<html><head>
		<link rel="stylesheet" type="text/css" href="../../css/base.css" />
		<link rel="stylesheet" type="text/css" href="../../css/rst.css" />
		<link rel="stylesheet" href="style.css" type="text/css" />
		</head><body>''')

	for c in classes:
		out.write('<a name="%s"></a><h2>%s %s</h2>' % (html_sanitize(c['name']), html_sanitize(c['type']), html_sanitize(c['name'])))
		print_declared_in(out, c)
		out.write('<p>%s</p>' % html_sanitize(c['desc']))

		out.write('<pre class="literal-block">')
		print >>out, '%s\n{' % html_sanitize(c['decl'])
		for f in c['fun']:
			print >>out, '   %s' % html_sanitize(f['signature'].replace('\n', '\n   '))

		if len(c['fun']) > 0 and len(c['enums']) > 0 and len(c['fields']) > 0: print >>out, ''

		first = True
		for e in c['enums']:
			if not first:
				print >>out, ''
			first = False
			print >>out,'   enum %s\n   {' % html_sanitize(e['name'])
			for v in e['values']:
				print >>out,'      %s' % html_sanitize(v['name'])
			print >>out,'   };'

		if len(c['fun']) + len(c['enums']) > 0 and len(c['fields']): print >>out, ''

		for f in c['fields']:
			print >>out, '   %s' % html_sanitize(f['signature'])

		out.write('};</pre>')

		# TODO: merge overloaded functions
		for f in c['fun']:
			if f['desc'] == '': continue
			print >>out, '<a name="%s"></a><h3>%s()</h3>' % (html_sanitize(f['name']), html_sanitize(f['name']))
			print >>out, '<blockquote><pre class="literal-block">%s</pre></blockquote>' % html_sanitize(f['signature'].replace('\n', '\n   '))
			print >>out, '<p>%s</p>' % html_sanitize(f['desc'])

		for e in c['enums']:
			if e['desc'] == '': continue
			print >>out, '<a name="%s::%s"></a><h3>enum %s</h3>' % (html_sanitize(e['name']), html_sanitize(c['name']), html_sanitize(e['name']))
			print >>out, '<table><tr><th>value</th><th>description</th></tr>'
			for v in e['values']:
				print >>out, '<tr><td>%s</td><td>%s</td></tr>' % (html_sanitize(v['name']), html_sanitize(v['desc']))
			print >>out, '</table>'

		for f in c['fields']:
			if f['desc'] == '': continue
			print >>out, '<a name="%s"></a><dt>%s</dt>' % (html_sanitize(c['name'] + '::' + f['name']), html_sanitize(f['name']))
			print >>out, '<dd>%s</dd>' % html_sanitize(f['desc'])


	# TODO: merge overloaded functions
	for f in functions:
		print >>out, '<a name="%s"></a><h2>%s()</h2>' % (html_sanitize(f['name']), html_sanitize(f['name']))
		print_declared_in(out, f)
		print >>out, '<blockquote><pre class="literal-block">%s</pre></blockquote>' % html_sanitize(f['signature'])
		print >>out, '<p>%s</p>' % html_sanitize(f['desc'])

	for e in enums:
		print >>out, '<a name="%s"></a><h2>enum %s</h2>' % (html_sanitize(e['name']), html_sanitize(e['name']))
		print_declared_in(out, e)
		print >>out, '<table><tr><th>value</th><th>description</th></tr>'
		for v in e['values']:
			print >>out, '<tr><td>%s</td><td>%s</td></tr>' % (html_sanitize(v['name']), html_sanitize(v['desc']))
		print >>out, '</table>'

	out.write('</body></html>')
	out.close()
