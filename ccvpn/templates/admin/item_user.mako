<%inherit file="../layout.mako" />

<section>
    <h2><a href="/admin/">Admin</a> - <a href="/admin/users">User</a> #${item.id} : ${item.username}</h2>
    <article class="two">
        <form class="largeform" action="/admin/users?id=${item.id}" method="post">
                <label for="f_id">ID</label>
                <input type="text" name="id" id="f_id" value="${item.id}" readonly="readonly" />

                <label for="f_username">Username</label>
                <input type="text" name="username" id="f_username" value="${item.username}" />
                
                <label for="f_password">Password</label>
                <input type="password" name="password" id="f_password" value="" placeholder="<empty to not change>" />
            
                <label for="f_email">E-mail</label>
                <input type="text" name="email" id="f_email" value="${item.email or ''}" />
            
                <label for="f_is_active">Active?</label>
                <input type="checkbox" name="is_active" id="f_is_active" ${ 'checked="checked"' if item.is_active else '' | n} />
            
                <label for="f_is_admin">Admin?</label>
                <input type="checkbox" name="is_admin" id="f_is_admin" ${ 'checked="checked"' if item.is_admin else '' | n} />
            
                <label for="f_signup_date">Signup</label>
                <input type="text" name="signup_date" id="f_signup_date" value="${item.signup_date or ''}" />
            
                <label for="f_last_login">Last login</label>
                <input type="text" name="last_login" id="f_last_login" value="${item.last_login or ''}" />
            
                <label for="f_paid_until">Paid until...</label>
                <input type="text" name="paid_until" id="f_paid_until" value="${item.paid_until or ''}" />
            <input type="submit" />
        </form>
    </article>
    <article class="two">
        <h3>Orders</h3>
        % if item.orders:
        <table>
            <tr><td>ID</td> <td>Time</td> <td>Paid?</td> <td>Method</td></tr>
            % for order in item.orders:
                <tr>
                    <td><a href="/admin/orders?id=${order.id}">${order.id}</a></td>
                    <td>${order.time}</td>
                    <td>${order.paid | check}</td>
                    <td>${order.method}</td>
                </tr>
            % endfor
        </table>
        % else:
            <p>None</p>
        % endif
    </article>
    <article class="two">
        <h3>Gift Codes Used</h3>
        % if item.giftcodes_used:
        <table>
            <tr><td>ID</td> <td>Code</td> <td>Time</td></tr>
            % for gc in item.giftcodes_used:
                <tr>
                    <td><a href="/admin/giftcodes?id=${gc.id}">${gc.id}</a></td>
                    <td>${gc.code}</td>
                    <td>${gc.time}</td>
                </tr>
            % endfor
        </table>
        % else:
            <p>None</p>
        % endif
    </article>
    <div style="clear: both"></div>
</section>
