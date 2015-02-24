$(document).ready(function () {
    $(window).trigger('hashchange');
    loadcomics();
    loadWanteds();
    loadHistory();

    $('#add_comic_button').click(function () {
        $(this).attr('disabled', true);
        searchForcomic($('#add_comic_name').val(), $('#add_comic_album').find('option:selected').val());
    });

    $('#add_comicid_button').click(function () {
        addcomic($('#add_comic_select').val(), $('#add_comic_album').find('option:selected').val(), $('#add_comic_select').find('option:selected').text())

    });

    $('#cancel_comic_button').click(function () {
        cancelAddcomic();
    });

    $('.mylar_forceprocess').click(function(e) {
        e.preventDefault();
        Postprocess();
    });

    $('#album-tracks .btn-search').click(function () {
        var $parentRow = $(this).parents('tr')
        var albumId = $parentRow.attr('data-albumid');
        var name = $(this).parents('tr').find('.comic').text();
        searchForAlbum(albumId, name);
    })
});

function searchForAlbum(albumId, name) {
    var modalcontent = $('<div>');
    modalcontent.append($('<p>').html('Looking for album &quot;'+ name +'&quot;.'));
    modalcontent.append($('<div>').html('<div class="progress progress-striped active"><div class="bar" style="width: 100%;"></div></div>'));
    showModal('Searching for album "'+ name + '"', modalcontent, {});

    $.ajax({
        url: WEBDIR + 'mylar/QueueAlbum?albumId=' + albumId,
        type: 'get',
        dataType: 'json',
        timeout: 40000,
        success: function (data) {
            // If result is not 'succes' it must be a failure
            if (data.result != 'success') {
                notify('Error', data.message, 'error');
            } else {
                notify('OK', name + ' ' + season + 'x'+episode+' found. ' + data.message, 'success');
            }
        },
        error: function (data) {
            notify('Error', 'Episode not found.', 'error', 1);
        },
        complete: function (data) {
            hideModal();
        }
    });
}

function beginRefreshcomic(comicId) {
    var $div = $('div').html('Refreshing comic');
    var $buttons = {
        'Refresh': function () {
            beginRefreshcomic(comicId);
        }
    }

    showModal('Refresh comic?', $div, $buttons);
}

function refreshcomic(comicId) {

    $.ajax({
        url: WEBDIR + 'mylar/Refreshcomic',
        type: 'post',
        data: {'comicId': comicId},
        dataType: 'json',
        success: function (result) {

        },
        error: function (req) {
            console.log('error refreshing comic');
        }
    })
}

function searchForcomic(name, type) {
    $.ajax({
        url: WEBDIR + 'mylar/SearchForcomic',
        type: 'get',
        data: {'name': name,
                'searchtype': type},
        dataType: 'json',
        timeout: 40000,
        success: function (result) {
            if (!result || result.length === 0) {
                $('#add_comic_button').attr('disabled', false);
                return;
            }
            // remove any old search
            $('#add_comic_select').html('');

            if (type == 'comicId') {
                $.each(result, function (index, item) {
                    var option = $('<option>')
                    .attr('value', item.id)
                    .html(item.uniquename);

                    $('#add_comic_select').append(option);
                });

            } else {
                $.each(result, function (index, item) {
                    var tt;
                    if (item.date.length) {
                        // release date should be (yyyy) or empty string
                        tt = ' (' + item.date.substring(0,4) + ') '
                    } else {
                        tt = '  '
                    }
                    // item.uniquename == comic name
                    if (item.uniquename === 'None') {
                        // to remove None..
                        item.uniquename = ''
                    }
                    var option = $('<option>')
                        .attr('value', item.albumid)
                        .html(item.title + tt + item.uniquename);

                    $('#add_comic_select').append(option);
                });
            }



            $('#add_comic_name').hide();
            $('#cancel_comic_button').show();
            $('#add_comic_select').fadeIn();
            $('#add_comic_button').attr('disabled', false).hide();
            $('#add_comicid_button').show();
        }
    })
}

function addcomic(id, searchtype, name) {
    // val can be comicId or albumId
    var stype = (searchtype === 'comicId') ? 'comic' : 'Album';
    $.ajax({
        url: WEBDIR + 'mylar/Addcomic',
        data: {'id': id,
               'searchtype': searchtype},
        type: 'get',
        dataType: 'json',
        success: function (data) {
            $('#add_comic_name').val('');
            notify('Add ' + stype, 'Successfully added  '+ stype + ' ' + name, 'success');
            cancelAddcomic();
        }
    })
}

function cancelAddcomic() {
    $('#add_comic_select').hide();
    $('#cancel_comic_button').hide();
    $('#add_comic_name').fadeIn();
    $('#add_comicid_button').hide();
    $('#add_comic_button').show();
}

function loadcomics() {
    $.ajax({
        url: WEBDIR + 'mylar/getserieslist',
        type: 'get',
        dataType: 'json',
        success: function (result) {
            if (result.length == 0) {
                var row = $('<tr>')
                row.append($('<td>').html('No comics found'));
                $('#comics_table_body').append(row);
            } else {
                $.each(result, function (index, comic) {
                    var image = $('<img>').addClass('img-polaroid img-rounded comicimgtab')
                    var name = $('<a>')
                        .attr('href',WEBDIR + 'mylar/viewcomic/' + comic.ComicID)
                        .text(comic.ComicName);
                    var row = $('<tr>')

                    var isError = comic.ComicName.indexOf('Fetch failed') != -1;
                    if (isError) {
                        comic.Status = 'Error';
                    }

                    var $statusRow = $('<td>')
                        .html(mylarStatusLabel(comic.Status));

                    if (isError) {
                        $statusRow.click(function () {
                            beginRefreshcomic(comic.ComicID);
                        });
                    }

                    if (comic.ThumbURL) {
                        // ComicImage
                        //image.attr('src', WEBDIR + 'mylar/GetThumb/?thumb=' + comic.ThumbURL)

                    } else {
                        image.attr('src', '../img/no-cover-comic.png').css({'width' : '64px' , 'height' : '64px'}) //TODO

                    }

                    var div = $('<div>').addClass("comicthumbdiv").append(image)
                    row.append(
                        $('<td>').append(div),
                        $('<td>').html(name),
                        $('<td>').append(comic.LatestAlbum),
                        $('<td>').append(comic.ReleaseDate),
                        $statusRow
                    );
                    $('#comics_table_body').append(row);
                });
                $('#comics_table_body').parent().trigger('update');
                $('#comics_table_body').parent().trigger("sorton",[[[0,0]]]);
            }
        }
    });
}

function loadWanteds() {
    // Clear it incase off reload
    $('#wanted_table_body').empty();
    $.ajax({
        url: WEBDIR + 'mylar/GetWantedList',
        type: 'get',
        dataType: 'json',
        success: function (result) {

            if (result.length == 0) {
                var row = $('<tr>')
                row.append($('<td>').attr('colspan', '5').html('No wanted issues found'));
                $('#wanted_table_body').append(row);
            } else {
                $.each(result, function (index, wanted) {
                    console.log(wanted)
                    var row = $('<tr>');
                    var image = $('<img>').addClass('img-polaroid img-rounded')
                    if (wanted.ThumbURL) {
                        image.attr('src', WEBDIR + 'mylar/GetThumb/?w=150&h=150&thumb=' + encodeURIComponent(wanted.ThumbURL))

                    } else {
                        image.attr('src', '../img/no-cover-comic.png').css({'width' : '75px' , 'height' : '75px'})

                    }

                    //var buttons = $('<div>').addClass('btn-group')
                    var remove = $('<a class="btn btn-mini btn-cancel" title="Set Skipped"><i class="icon-step-forward"></i></a></td>').click(function () {
                                $.ajax({
                                    url: WEBDIR + 'mylar/UnqueueAlbum',
                                    data: {'albumId': wanted.ComicID},
                                    type: 'get',
                                    complete: function (result) {
                                        loadWanteds()
                                        notify('Set Skipped', wanted.ComicName + ' - ' + wanted.IssueName);
                                    }
                                })
                            })
                    var search = $('<a class="btn btn-mini" title="Set wanted"><i class="icon-heart"></i></a></td>').click(function () {
                                $.ajax({
                                    url: WEBDIR + 'mylar/QueueAlbum',
                                    data: {'albumId': wanted.ComicID},
                                    type: 'get',
                                    complete: function (result) {
                                        notify('Set wanted', wanted.ComicName + ' - ' + wanted.IssueName);
                                    }
                                })
                            })
                    var force = $('<a class="btn btn-mini" title="Force Check"><i class="icon-search"></i></a></td>').click(function () {
                                $.ajax({
                                    url: WEBDIR + 'mylar/QueueAlbum&new=True',
                                    data: {'albumId': wanted.ComicID},
                                    type: 'get',
                                    complete: function (result) {
                                        notify('Force Check', wanted.ComicName + ' - ' + wanted.IssueName);
                                    }
                                })
                            })


                    var div = $('<div>').addClass('btn-group').append(search, force, remove);
                    row.append(
                        $('<td>').append(
                            $('<a>')
                                .addClass('mylar_wanted_comicname')
                                .attr('href', WEBDIR + 'mylar/viewcomic/' + wanted.ComicID)
                                .text(wanted.ComicName)),
                        $('<td>').append(
                            $('<a>')
                                .addClass('mylar_wanted_comicalbum')
                                .attr('href', WEBDIR + 'mylar/viewissue/' + wanted.IssueID)
                                .text(wanted.IssueName)),
                        $('<td>').text(wanted.Issue_Number),
                        $('<td>').text(wanted.ReleaseDate),
                        $('<td>').append(mylarStatusLabel(wanted.Status)),
                        $('<td>').append(div)
                        /*
                        $('<td><a class="btn btn-mini"><i class="icon-remove-circle"></i></a></td>')


                                $.get(WEBDIR + 'mylar/UnqueueAlbum', {'albumId': wanted.AlbumID}, function(r) {
                                    alert(r);
                                    if (r === "OK") {
                                        $(this).closest('tr').remove();
                                    }
                                });

                            })
                        */

                    );
                    $('#wanted_table_body').append(row);
                });
                $('#wanteds_table_body').parent().trigger('update');
                $('#wanteds_table_body').parent().trigger("sorton",[[[0,0]]]);
            }
        }
    })
}

function loadHistory() {
    $.ajax({
        url: WEBDIR + 'mylar/GetHistoryList',
        type: 'get',
        dataType: 'json',
        success: function(result) {
            if (result.length == 0) {
                var row = $('<tr>')
                row.append($('<td>').html('History is empty'));
                $('#history_table_body').append(row);
            }
            $.each(result, function(i, item) {
                var row = $('<tr>');
                row.append(
                    $('<td>').html(item.DateAdded),
                    $('<td>').html(item.Title),
                    $('<td>').html(mylarStatusLabel(item.Status))
                );
                $('#history_table_body').append(row);
            });
        }
    });
}

function loadHistory() {
    $.ajax({
        url: WEBDIR + 'mylar/GetHistoryList',
        type: 'get',
        dataType: 'json',
        success: function(result) {
            if (result.length === 0) {
                var row = $('<tr>')
                row.append($('<td>').html('History is empty'));
                $('#history_table_body').append(row);
            }
            $.each(result, function(i, item) {
                var row = $('<tr>');
                row.append(
                    $('<td>').html(item.DateAdded),
                    $('<td>').html(item.Title),
                    $('<td>').html(mylarStatusLabel(item.Status))
                );
                $('#history_table_body').append(row);
            });
        }
    });
}

function mylarStatusLabel(text) {
    var statusOK = ['Active', 'Downloaded', 'Processed'];
    var statusInfo = ["Wanted"];
    var statusError = ['Paused', 'Unprocessed'];
    var statusWarning = ['Skipped', 'Custom', 'Snatched'];

    var label = $('<span>').addClass('label').text(text);

    if (statusOK.indexOf(text) != -1) {
        label.addClass('label-success');
    } else if (statusInfo.indexOf(text) != -1) {
        label.addClass('label-info');
    } else if (statusError.indexOf(text) != -1) {
        label.addClass('label-important');
    } else if (statusWarning.indexOf(text) != -1) {
        label.addClass('label-warning');
    }

    var icon = mylarStatusIcon(text, true);
    if (icon !== '') {
        label.prepend(' ').prepend(icon);
    }
    return label;
}


var mylarStatusMap = {
    'Active': 'icon-repeat',
    'Error': 'icon-bell',
    'Paused': 'icon-pause',
    'Snatched': 'icon-share-alt',
    'Skipped': 'icon-fast-forward',
    'Wanted': 'icon-heart',
    'Processed': 'icon-ok',
    'Unprocessed': 'icon-exclamation-sign'
}
function mylarStatusIcon(iconText, white){
    var iconClass = mylarStatusMap[iconText];

    if (typeof iconClass == 'undefined') {
        return;
    }

    var icon = $('<i>').addClass(iconClass);

    if (white == true) {
        icon.addClass('icon-white');
    }
    return icon;
}

function Postprocess() {
    var data = {};
    p = prompt('Write path to processfolder or leave blank for default path');
    if (p || p.length >= 0) {
        data.dir = p;

        $.get(WEBDIR + 'mylar/ForceProcess', data, function(r) {
            state = (r.length) ? 'success' : 'error';
            // Stop the notify from firing on cancel
            if (p !== null) {
                path = (p.length === 0) ? 'Default folder' : p;
                notify('mylar', 'Postprocess ' + path, state);
            }
        });

    }
}