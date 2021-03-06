<%inherit file="../layout.mako" />

<section>
    <h2><a href="/admin/">Admin</a> - <a href="/admin/${model_name.lower()}s">${model_name}</a> - ${str(item)} #${item.id}</h2>
    <article>
        <form class="largeform" action="/admin/${model_name.lower()}s?id=${item.id}" method="post">
        % for field in model.edit_fields:
            <%
                doc = getattr(model, field).__doc__
                value = getattr(item, field)
                if value is None:
                    value = ''
            %>
            % if isinstance(value, bool):
                <label for="f_${field}">${doc if doc is not None else field}</label>
                <input type="checkbox" name="${field}" id="f_${field}" ${'checked="checked"' if value else ''} />
            % else:
                <label for="f_${field}">${doc if doc is not None else field}</label>
                <input type="text" name="${field}" id="f_${field}" value="${value}" />
            % endif
        % endfor
            <input type="submit" />
        </form>
    </article>
    <div style="clear: both"></div>
</section>
