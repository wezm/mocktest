"""
MockWrapper objects are to be used in test code. They allow
behaviour and expectations to be set on a SilentMock.

A wrapper can be created for an existing SilentMock with
mock_wrapper(silent_mock).

A MockWrapper / SilentMock pair can be created with mock_wrapper()
(the silent mock object is accessible via mock_wrapper()_)
"""

from lib.realsetter import RealSetter
from silentmock import SilentMock, raw_mock
from mockmatcher import MockMatcher
from mockerror import MockError

def mock_wrapper(mock = None, proxied = None):
	"""
	return a mock wrapper for the given silent mock, delegating to `proxied`
	when a given call is not set to be intercepted by the mock. You can use
	the mock wrapper to set expectations or get invocation details for a silent mock
	"""
	if mock is None:
		mock = raw_mock()
	if (not isinstance(mock, SilentMock)) and proxied is None:
		# make mock_wrapper(real_obj) act like mock_wrapper(None, proxied=real_obj)
		proxied = mock
		mock = raw_mock()
	return MockWrapper(mock, proxied)

class MockWrapper(RealSetter):
	"""
	a mock object wrapper for use in test cases
	 - allows expectations and mock actions to be set
	
	all setattr and getattr go via the attahced silent mock's _mock_get and _mock_set
	"""
	_all_expectations = None
	def __init__(self, wrapped_mock = None, proxied = None):
		if self.__class__._all_expectations is None:
			raise RuntimeError(("%s._setup has not been called. " +
				"Make sure you are inheriting from mock.TestCase, " +
				"not unittest.TestCase") % (self.__class__.__name__,))
		if wrapped_mock is None:
			wrapped_mock = raw_mock()
		if not isinstance(wrapped_mock, SilentMock):
			raise TypeError("expected SilentMock, got %s" % (wrapped_mock.__class__.__name__,))
		self._real_set(_mock = wrapped_mock)
		self._proxied = proxied
	
	# delegate getting and setting to SilentMock
	def _set(self, **kwargs):
		self.mock._mock_set(**kwargs)
	
	def _get(self, attr):
		return self.mock._mock_get(attr)
	
	def _get_mock(self):
		return self._mock
	mock = property(_get_mock)
			
	# mockExpecation integration
	@classmethod
	def _setup(cls):
		if not cls._all_expectations is None:
			raise RuntimeError("%s._setup been called twice in a row"
				% (cls.__name__,))
		cls._all_expectations = []
	
	@classmethod
	def _teardown(cls):
		if cls._all_expectations is None:
			raise RuntimeError("%s._teardown been called twice in a row"
				% (cls.__name__,))
		try:
			for expectation in cls._all_expectations:
				assert expectation, expectation
		finally:
			cls._all_expectations = None

	def __called_matcher(self):
		return MockMatcher(self.mock)
	called = property(__called_matcher)
	
	def __expect_call_on(self, obj):
		matcher = MockMatcher(obj)
		self.__class__._all_expectations.append(matcher)
		return matcher
	
	def __expect_call_matcher(self):
		return self.__expect_call_on(self.mock)
	is_expected = property(__expect_call_matcher)

	def expects(self, methodname):
		return self.__expect_call_on(getattr(self.mock, methodname))

	def __str__(self):
		return 'mock wrapper for \"%s\"' %(self._get('name'))

	def __setattr__(self, attr, val):
		self.mock._mock_set(**{attr:val})

	def __getattr__(self, attr):
		return self.mock._mock_get(attr)
		
	def __delattr__(self, attr):
		self.mock._mock_del(attr)
	
	def reset(self):
		self.mock._mock_reset()
	
	def child(self, val):
		return mock_wrapper(getattr(self.mock, val))
	
	def with_special(self, **kwargs):
		self.mock._mock_set_special(**kwargs)
		return self
		
	# convenience methods for dsl-like chaining
	def returning(self, val):
		self.return_value = val
		return self

	def named(self, val):
		self.name = val
		return self
	
	def with_action(self, val):
		self.action = val
		return self
	
	# selectively proxy calls; when should_intercept returns false then the
	# original (proxied) object is actually called, and no call on the mock is recorded
	def with_args(self, *args, **kwargs):
		self._ensure_can_set_intercept()
		self.should_intercept = lambda *a, **k: a == args and k == kwargs
		return self
	with_ = with_args

	def when_args(self, predicate):
		self._ensure_can_set_intercept()
		self.should_intercept = predicate
		return self
	when_ = when_args
	
	def _ensure_can_set_intercept(self):
		if self.should_intercept is not True:
			raise MockError("an interception condition (`with_args` or `where_args`) has already been set on mock %r" % (self.mock))

	def raising(self, ex):
		def mock_raise(*args, **kwargs):
			raise ex
		return self.with_action(mock_raise)

	def with_spec(self, spec):
		children = [member for member in dir(spec) if not 
			(member.startswith('__') and member.endswith('__'))]
		return self.with_children(*children)
	
	def with_methods(self, *methods, **kwmethods):
		self._with_children(*methods)
		for key in kwmethods:
			kwmethods[key] = raw_mock(return_value = kwmethods[key])
		return self.with_children(**kwmethods)
	
	def with_children(self, *children, **kwchildren):
		self._with_children(*children, **kwchildren)
		return self.frozen()
	
	def _with_children(self, *children, **kwchildren):
		"""internally add children, but don't freeze the mock"""
		for child in children:
			getattr(self.mock, child)
		for child, val in kwchildren.items():
			setattr(self.mock, child, val)
		return self
	
	def frozen(self):
		self._modifiable_children = False
		return self

	def unfrozen(self):
		self._modifiable_children = True
		return self
