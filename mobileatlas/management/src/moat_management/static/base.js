'use strict';

$(document).ready(function(){
    $('.show').click(function(){
        $(this).siblings().show();
        $(this).hide();
    });

    $('.timestamp').map(function(idx, elem){
        const ts = Date.parse(elem.textContent);
        
        if (ts) {
            // https://stackoverflow.com/questions/12413243/javascript-date-format-like-iso-but-local
            elem.textContent = new Date(ts)
                .toLocaleString("sv", {timeZoneName:'longOffset'})
                .replace(' ', 'T')
                .replace(' GMT', '');
        }
    });

    $('#change-probe-name').click(function(){
        var probe_id = $("#probe-id").val();
        var name = $("#change-probe-name-text").val();

        if (!probe_id) {
            alert("Please select a probe.");
            return;
        }

        $.ajax({
            url: '/probe/'+probe_id+'/change_name/'+name,
            type: 'post',
            success: function(result){
                location.reload();
            }
        });
    });

    $('#change-probe-country').click(function(){
        const probe_id = $('#probe-id').val();

        if (!probe_id) {
            alert("Please select a probe.");
            return;
        }

        const country = $('#change-probe-country-text').val();
        $.ajax({
            url: '/probe/' + probe_id + '/change_country',
            type: 'post',
            data: JSON.stringify({'country': country}),
            contentType: 'application/json',
            success: function(result){
                location.reload();
            },
            error: function(result){
                alert(result.status + ' ' + result.responseText);
            }
        });
    });

    $('.execute-probe').click(function(){
        var probe_id = $("#probe-id").val();
        var name = $(this).data('command');
        $.ajax({
            url: '/probe/'+probe_id+'/execute/'+name,
            type: 'post',
            success: function(result){
                location.reload();
            }
        });
    });

    $('.deactivate-token-btn').click(function(ev){
        const row = ev.delegateTarget.parentElement;
        const token = $('.token', row).val();

        const confirm_text = $('.confirm-text', row).val();

        const res = prompt(`To permanently delete the token (and corresponding configuration) type the following: '${confirm_text}'`);
        if (res !== confirm_text) {
          return;
        }

        $.ajax({
            url: '/tokens/deactivate',
            type: 'post',
            data: JSON.stringify({'token': token}),
            contentType: 'application/json',
            success: function(result){
                location.reload();
            },
            error: function(result){
                alert(result.status + ' ' + result.responseText);
            }
        });
    });

    $('.activate-token-btn').click(function(ev){
        const row = ev.delegateTarget.parentElement;
        const token = $('.token', row).val();
        const scope = $('.token-scope', row).val();

        let data = {'token_candidate': token, 'scope': Number(scope)};

        if (scope & 1) {
            data['ip'] = prompt('IP');
        }
        if (scope & 2) {
            data['name'] = prompt('Probe name');
        }

        $.ajax({
            url: '/tokens/activate',
            type: 'post',
            data: JSON.stringify(data),
            contentType: 'application/json',
            success: function(result){
                location.reload();
            },
            error: function(result){
                alert(result.status + ' ' + result.responseText);
            }
        });
    });

    $('#add-token').click(function(ev){
        const token = $('#token').val();
        let scope = 0;
        for (const e of $('.scope-chbx')) {
            if (e.checked) { scope |= e.value; }
        }
        let data = {'token_candidate': token, 'scope': Number(scope)};

        const ip = $('#WgBox')[0].checked ? $('#ipIn').val() : undefined;
        if (ip) { data['ip'] = ip; }

        const name = $('#PrBox')[0].checked ? $('#PrNameIn').val() : undefined;
        if (name) { data['name'] = name; }

        $.ajax({
            url: '/tokens/activate',
            type: 'post',
            data: JSON.stringify(data),
            contentType: 'application/json',
            success: function(result){
                location.reload();
            },
            error: function(result){
                alert(result.status + ' ' + result.responseText);
            }
        });
    });

    $('#add-tunnel-token').click(function(ev){
        const admin = $('#ttoken-admin')[0].checked;
        const scope = $('#ttoken-scope').val();

        let data = {'admin': admin, 'scope': Number(scope)};

        $.ajax({
            url: '/tunnel/token',
            type: 'post',
            data: JSON.stringify(data),
            contentType: 'application/json',
            success: function(result){
                location.reload();
            },
            error: function(result){
                alert(result.status + ' ' + result.responseText);
            }
        });
    });

    $('#allow-sim').click(function(ev){
        const token = Number($('#tsim-token').val());
        const imsi = $('#tsim-imsi').val();
        const iccid = $('#tsim-iccid').val();
        const pub = $('#tsim-public')[0].checked;
        const provide = $('#tsim-provide')[0].checked;
        const request = $('#tsim-request')[0].checked;

        let data = {
            'public': pub,
            'provide': provide,
            'request': request,
        };

        if (imsi) { data['imsi'] = imsi; }
        if (iccid) { data['iccid'] = iccid; }

        $.ajax({
            url: `/tunnel/token/${token}/sim`,
            type: 'post',
            data: JSON.stringify(data),
            contentType: 'application/json',
            success: function(result){
                location.reload();
            },
            error: function(result){
                alert(result.status + ' ' + result.responseText);
            }
        });
    });
});
