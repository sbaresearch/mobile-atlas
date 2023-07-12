$(document).ready(function(){
    $('.show').click(function(){
        $(this).siblings().show();
        $(this).hide();
    });

    $('#register-probe').click(function(){
        var mac = $("#register-probe-mac").val();
        $.ajax({
            url: '/probe/register',
            data: {'mac': mac},
            type: 'post',
            success: function(result){
                window.location.reload();
            },
            error: function(result){
                alert(result.status + ' ' + result.responseText);
            }
        });
    });

    $('#activate-probe').click(function(){
        var probe_id = $("#probe-id").val();

        $.ajax({
            url: '/probe/'+probe_id+'/activate',
            type: 'post',
            success: function(result){
                location.reload();
            }
        });
    });

    $('#deactivate-probe').click(function(){
        var probe_id = $("#probe-id").val();

        $.ajax({
            url: '/probe/'+probe_id+'/deactivate',
            type: 'post',
            success: function(result){
                location.reload();
            }
        });
    });

    $('#change-probe-name').click(function(){
        var probe_id = $("#probe-id").val();
        var name = $("#change-probe-name-text").val();
        $.ajax({
            url: '/probe/'+probe_id+'/change_name/'+name,
            type: 'post',
            success: function(result){
                location.reload();
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

    $('#allow-wireguard').click(function(){
        var mac = $("#allow-wireguard-mac").val();
        var ip = $("#allow-wireguard-ip").val();
        $.ajax({
            url: '/wireguard/allow',
            data: {'mac': mac, 'ip': ip},
            type: 'post',
            success: function(result){
                location.reload();
            },
            error: function(result){
                alert(result.status + ' ' + result.responseText);
            }
        });
    });

    $('#disallow-wireguard').click(function(){
        var mac = $("#allow-wireguard-mac").val();
        $.ajax({
            url: '/wireguard/disallow',
            data: {'mac': mac},
            type: 'post',
            success: function(result){
                location.reload();
            },
            error: function(result){
                alert(result.status + ' ' + result.responseText);
            }
        });
    });

});