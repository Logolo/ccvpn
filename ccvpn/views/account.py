import datetime

import transaction
from sqlalchemy import func
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from pyramid.view import view_config, forbidden_view_config
from pyramid.renderers import render, render_to_response
from pyramid.httpexceptions import (
    HTTPSeeOther, HTTPMovedPermanently,
    HTTPBadRequest, HTTPNotFound, HTTPUnauthorized, HTTPForbidden, HTTPFound
)
from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message

from ccvpn import methods
from ccvpn.models import (
    DBSession,
    GiftCode, AlreadyUsedGiftCode,
    User, Order, Profile, PasswordResetToken,
    random_access_token
)


# Set in __init__.py from app settings
openvpn_gateway = ''
openvpn_ca = ''


@forbidden_view_config()
def forbidden(request):
    if not request.user:
        return HTTPFound(location=request.route_url('account_login'))
    return HTTPForbidden()


@view_config(route_name='account_login', renderer='login.mako')
def login(request):
    if request.method != 'POST':
        return {}

    username = request.POST.get('username')
    password = request.POST.get('password')
    if not username or not password:
        request.response.status_code = HTTPBadRequest.code
        return {}

    user = DBSession.query(User).filter_by(username=username).first()
    if not user or not user.check_password(password):
        request.response.status_code = HTTPForbidden.code
        request.messages.error('Invalid username or password.')
        return {}

    request.session['uid'] = user.id
    request.messages.info('Logged in.')
    return HTTPSeeOther(location=request.route_url('account'))


@view_config(route_name='account_logout', permission='logged')
def logout(request):
    if 'uid' in request.session:
        del request.session['uid']
        request.session.flash(('info', 'Logged out.'))
    return HTTPSeeOther(location=request.route_url('home'))


@view_config(route_name='account_signup', renderer='signup.mako')
def signup(request):
    if request.method != 'POST':
        return {}
    errors = []

    try:
        username = request.POST.get('username')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        email = request.POST.get('email')

        if not User.validate_username(username):
            errors.append('Invalid username.')
        if not User.validate_password(password):
            errors.append('Invalid password.')
        if email and not User.validate_email(email):
            errors.append('Invalid email address.')
        if password != password2:
            errors.append('Both passwords do not match.')

        assert not errors

        used = User.is_used(username, email)
        if used[0] > 0:
            errors.append('Username already registered.')
        if used[1] > 0 and email:
            errors.append('E-mail address already registered.')

        assert not errors

        with transaction.manager:
            u = User(username=username, email=email, password=password)
            if request.referrer:
                u.referrer_id = request.referrer.id
            DBSession.add(u)
        request.session['uid'] = u.id
        return HTTPSeeOther(location=request.route_url('account'))
    except AssertionError:
        for error in errors:
            request.session.flash(('error', error))
        fields = ('username', 'password', 'password2', 'email')
        request.response.status_code = HTTPBadRequest.code
        return {k: request.POST[k] for k in fields}


@view_config(route_name='account_forgot', renderer='forgot_password.mako')
def forgot(request):
    if request.method != 'POST' or 'username' not in request.POST:
        return {}

    u = DBSession.query(User) \
        .filter_by(username=request.POST['username']) \
        .first()
    if not u:
        request.messages.error('Unknown username.')
        request.response.status_code = HTTPBadRequest.code
        return {}
    if not u.email:
        request.messages.error('No e-mail address associated with username.')
        request.response.status_code = HTTPBadRequest.code
        return {}

    token = PasswordResetToken(u)
    with transaction.manager:
        DBSession.add(token)

    mailer = get_mailer(request)
    body = render('mail/password_reset.mako', {
        'user': u,
        'requested_by': request.remote_addr,
        'url': request.route_url('account_reset', token=token.token)
    })
    message = Message(subject='CCVPN: Password reset request',
                      recipients=[u.email],
                      body=body)
    mailer.send(message)
    request.messages.info('We sent a reset link. Check your emails.')
    return {}


@view_config(route_name='account_reset', renderer='reset_password.mako')
def reset(request):
    token = DBSession.query(PasswordResetToken) \
        .filter_by(token=request.matchdict['token']) \
        .first()

    if not token or not token.user:
        request.messages.error('Unknown password reset token.')
        url = request.route_url('account_forgot')
        return HTTPMovedPermanently(location=url)
    
    password = request.POST.get('password')
    password2 = request.POST.get('password2')

    if request.method != 'POST' or not password or not password2:
        return {'token': token}

    if not User.validate_password(password) or password != password2:
        request.messages.error('Invalid password.')
        request.response.status_code = HTTPBadRequest.code
        return {'token': token}

    token.user.set_password(password)

    mailer = get_mailer(request)
    body = render('mail/password_reset_done.mako', {
        'user': token.user,
        'changed_by': request.remote_addr,
    })
    message = Message(subject='CCVPN: Password changed',
                      recipients=[token.user.email],
                      body=body)
    mailer.send(message)

    request.messages.info('You have changed the password for %s. You can now '
                          'log in.' % (token.user.username))
    transaction.commit()
    with transaction.manager:
        DBSession.delete(token)
    url = request.route_url('account_login')
    return HTTPMovedPermanently(location=url)


@view_config(route_name='account', request_method='POST', permission='logged',
             renderer='account.mako')
def account_post(request):
    # TODO: Fix that. split in two functions or something.
    errors = []
    try:
        if 'profilename' in request.POST:
            p = Profile()
            p.validate_name(request.POST['profilename']) or \
                errors.append('Invalid name.')
            assert not errors
            name_used = DBSession.query(Profile) \
                .filter_by(uid=request.user.id,
                           name=request.POST['profilename']) \
                .first()
            if name_used:
                errors.append('Name already used.')
            profiles_count = DBSession.query(func.count(Profile.id)) \
                .filter_by(uid=request.user.id).scalar()
            if profiles_count > 10:
                errors.append('You have too many profiles.')
            assert not errors
            p.name = request.POST['profilename']
            p.askpw = 'askpw' in request.POST and request.POST['askpw'] == '1'
            p.uid = request.user.id
            if not p.askpw:
                p.password = random_access_token()
            DBSession.add(p)
            DBSession.flush()
            return account(request)

        if 'profiledelete' in request.POST:
            p = DBSession.query(Profile) \
                .filter_by(id=int(request.POST['profiledelete'])) \
                .filter_by(uid=request.user.id) \
                .first()
            assert p or errors.append('Unknown profile.')
            DBSession.delete(p)
            DBSession.flush()
            return account(request)

        u = request.user
        if request.POST['password'] != '':
            u.validate_password(request.POST['password']) or \
                errors.append('Invalid password.')
            if request.POST['password'] != request.POST['password2']:
                errors.append('Both passwords do not match.')
        if request.POST['email'] != '':
            u.validate_email(request.POST['email']) or \
                errors.append('Invalid email address.')
        assert not errors

        new_email = request.POST.get('email')
        if new_email and new_email != request.user.email:
            c = DBSession.query(func.count(User.id).label('ec')) \
                .filter_by(email=new_email).first()
            if c.ec > 0:
                errors.append('E-mail address already registered.')
        assert not errors
        if request.POST['password'] != '':
            u.set_password(request.POST['password'])
        if request.POST['email'] != '':
            u.email = request.POST['email']
        request.session.flash(('info', 'Saved!'))
        DBSession.flush()

    except KeyError:
        return HTTPBadRequest()
    except AssertionError:
        for error in errors:
            request.session.flash(('error', error))
    return account(request)


@view_config(route_name='account', permission='logged',
             renderer='account.mako')
def account(request):
    return {'email': request.user.email}


@view_config(route_name='account_redirect')
def account_redirect(request):
    return HTTPMovedPermanently(location=request.route_url('account'))


def order_post_gc(request, code):
    try:
        gc = GiftCode.one(code=code)
        gc.use(request.user)

        time = gc.time.days
        request.messages.info('OK! Added %d days to your account.' % time)
        DBSession.flush()
    except (NoResultFound, MultipleResultsFound):
        request.messages.error('Unknown code.')
    except AlreadyUsedGiftCode:
        request.messages.error('Already used code')
    return HTTPSeeOther(location=request.route_url('account'))

@view_config(route_name='order_post', permission='logged')
def order_post(request):
    code = request.POST.get('code')
    if code:
        return order_post_gc(request, code)

    times = (1, 3, 6, 12)
    try:
        method_name = request.POST.get('method')
        time_months = int(request.POST.get('time'))
    except ValueError:
        return HTTPBadRequest('invalid POST data')
    if method_name not in methods.METHODS or time_months not in times:
        return HTTPBadRequest('Invalid method/time')

    time = datetime.timedelta(days=30 * time_months)
    o = Order(user=request.user, time=time, amount=0, method=0)
    o.close_date = datetime.datetime.now() + datetime.timedelta(days=7)
    o.paid = False
    o.payment = {}
    method = methods.METHODS[method_name]()
    method.init(request, o)
    DBSession.add(o)
    DBSession.flush()
    return method.start(request, o)


@view_config(route_name='order_view', renderer='order.mako',
             permission='logged')
def order_view(request):
    id = int(request.matchdict['hexid'], 16)
    o = DBSession.query(Order).filter_by(id=id).first()
    if not o:
        return HTTPNotFound()
    if not request.user.is_admin and request.user.id != o.uid:
        return HTTPUnauthorized()
    return {'o': o}


@view_config(route_name='order_callback')
def order_callback(request):
    id = int(request.matchdict['hexid'], 16)
    o = DBSession.query(Order).filter_by(id=id).first()
    if not o:
        return HTTPNotFound()
    method = methods.METHOD_IDS[o.method]
    ret = method().callback(request, o)
    DBSession.flush()
    return ret


@view_config(route_name='config', permission='logged')
def config(request):
    r = render_to_response('config.ovpn.mako', dict(
        username=request.user.username,
        gateway=openvpn_gateway, openvpn_ca=openvpn_ca,
        android='android' in request.GET
    ))
    r.content_type = 'test/plain'
    return r


@view_config(route_name='config_profile', permission='logged')
def config_profile(request):
    pname = request.matchdict['profile']
    profile = DBSession.query(Profile) \
        .filter_by(uid=request.user.id, name=pname) \
        .first()
    if not profile:
        return HTTPNotFound()
    r = render_to_response('config.ovpn.mako', dict(
        username=request.user.username, profile=profile,
        gateway=openvpn_gateway, openvpn_ca=openvpn_ca,
        android='android' in request.GET
    ))
    r.content_type = 'test/plain'
    return r

