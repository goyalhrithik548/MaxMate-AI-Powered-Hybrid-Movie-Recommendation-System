// TRACKING VARIABLES
var entryTime = 0;
var currentMovieTitle = "";

$(function() {
  const source = document.getElementById('autoComplete');
  const inputHandler = function(e) {
    if(e.target.value==""){
      $('.movie-button').attr('disabled', true);
    }
    else{
      $('.movie-button').attr('disabled', false);
    }
  }
  source.addEventListener('input', inputHandler);

  // SEARCH CLICK
  $('.movie-button').on('click',function(){
    logTime(); // Log previous interaction before searching
    var my_api_key = '8265bd1679663a7ea12ac168da84d2e8';
    var title = $('#autoComplete').val();
    if (title=="") {
      $('.results').css('display','none');
      $('.fail').css('display','block');
    }
    else{
      $('.hero').hide();
      $('.main-content').hide();
      $('.results').css('display', 'none');
      $("#loader").fadeIn();
      load_details(my_api_key,title);
    }
  });

  // BACK BUTTON CLICK
  $(document).on('click', '.back-btn', function() {
      logTime(); // Log interaction before going back
  });
});

// LOGGING FUNCTION
function logTime() {
    if (entryTime > 0 && currentMovieTitle !== "") {
        var timeSpent = (Date.now() - entryTime) / 1000;
        // Send data
        navigator.sendBeacon("/log_interaction", JSON.stringify({
            title: currentMovieTitle,
            duration: timeSpent
        }));
        // Reset
        entryTime = 0;
        currentMovieTitle = "";
    }
}

// HANDLE TAB CLOSE
window.addEventListener("visibilitychange", function() {
    if (document.visibilityState === 'hidden') {
        logTime();
    }
});

function recommend(title, id) {
    logTime(); // Log previous before opening new
    var my_api_key = '8265bd1679663a7ea12ac168da84d2e8';
    $('.hero').hide();
    $('.main-content').hide();
    $("#loader").fadeIn();

    if (id && id !== 'undefined' && id !== 'None') {
        movie_recs(title, id, my_api_key, title);
    } else {
        load_details(my_api_key, title);
    }
    $(window).scrollTop(0);
}

function recommendcard(e) {
    var title = e.getAttribute('title');
    recommend(title, null);
}

function load_details(my_api_key,title){
  $.ajax({
    type: 'GET',
    url:'https://api.themoviedb.org/3/search/movie?api_key='+my_api_key+'&query='+title,
    success: function(movie){
      if(movie.results.length<1){
        $('.fail').css('display','block');
        $('.results').css('display','none');
        $("#loader").delay(500).fadeOut();
      }
      else{
        $("#loader").fadeIn();
        $('.fail').css('display','none');
        var movie_id = movie.results[0].id;
        var movie_title = movie.results[0].title;
        var movie_original_title = movie.results[0].original_title;
        movie_recs(movie_title, movie_id, my_api_key, movie_original_title);
      }
    },
    error: function(){
      alert('Invalid Request');
      $("#loader").delay(500).fadeOut();
    },
  });
}

function movie_recs(movie_title, movie_id, my_api_key, movie_original_title){
  $.ajax({
    type:'POST',
    url:"/similarity",
    data:{'name':movie_title},
    success: function(recs){
      if(recs=="Sorry! try another movie name"){
        $('.fail').css('display','block');
        $('.results').css('display','none');
        $("#loader").delay(500).fadeOut();
      }
      else {
        $('.fail').css('display','none');
        $('.results').css('display','block');
        var movie_arr = recs.split('---');
        var arr = [];
        for(const movie in movie_arr){
          arr.push(movie_arr[movie]);
        }
        get_movie_details(movie_id, my_api_key, arr, movie_original_title);
      }
    },
    error: function(){
      alert("Error getting recommendations");
      $("#loader").fadeOut();
    },
  });
}

function get_movie_details(movie_id, my_api_key, arr, display_title) {
  $.ajax({
    type:'GET',
    url:'https://api.themoviedb.org/3/movie/'+movie_id+'?api_key='+my_api_key,
    success: function(movie_details){
      show_details(movie_details, arr, display_title, my_api_key, movie_id);
    },
    error: function(){
      alert("API Error!");
      $("#loader").fadeOut();
    },
  });
}

function show_details(movie_details,arr,movie_title,my_api_key,movie_id){
  var imdb_id = movie_details.imdb_id;
  var poster = 'https://image.tmdb.org/t/p/original'+movie_details.poster_path;
  var overview = movie_details.overview;
  var genres = movie_details.genres;
  var rating = movie_details.vote_average;
  var vote_count = movie_details.vote_count;
  var release_date = new Date(movie_details.release_date);
  var runtime = parseInt(movie_details.runtime);
  var status = movie_details.status;
  var genre_list = []
  for (var genre in genres){
    genre_list.push(genres[genre].name);
  }
  var my_genre = genre_list.join(", ");
  if(runtime%60==0){
    runtime = Math.floor(runtime/60)+"h"
  }
  else {
    runtime = Math.floor(runtime/60)+"h "+(runtime%60)+"m"
  }

  var arr_poster = get_movie_posters(arr,my_api_key);
  var movie_cast = get_movie_cast(movie_id,my_api_key);
  var ind_cast = get_individual_cast(movie_cast,my_api_key);

  details = {
    'movie_id': movie_id,
    'title':movie_title,
      'cast_ids':JSON.stringify(movie_cast.cast_ids),
      'cast_names':JSON.stringify(movie_cast.cast_names),
      'cast_chars':JSON.stringify(movie_cast.cast_chars),
      'cast_profiles':JSON.stringify(movie_cast.cast_profiles),
      'cast_bdays':JSON.stringify(ind_cast.cast_bdays),
      'cast_bios':JSON.stringify(ind_cast.cast_bios),
      'cast_places':JSON.stringify(ind_cast.cast_places),
      'imdb_id':imdb_id,
      'poster':poster,
      'genres':my_genre,
      'overview':overview,
      'rating':rating,
      'vote_count':vote_count.toLocaleString(),
      'release_date':release_date.toDateString().split(' ').slice(1).join(' '),
      'runtime':runtime,
      'status':status,
      'rec_movies':JSON.stringify(arr),
      'rec_posters':JSON.stringify(arr_poster),
  }

  $.ajax({
    type:'POST',
    data:details,
    url:"/recommend",
    dataType: 'html',
    complete: function(){
      $("#loader").delay(500).fadeOut();
    },
    success: function(response) {
      $('.hero').hide();
      $('.main-content').hide();
      $('.results').show();
      $('.results').html(response);
      $('#autoComplete').val('');
      $(window).scrollTop(0);

      // START TIMER
      entryTime = Date.now();
      currentMovieTitle = movie_title;
    }
  });
}

function get_individual_cast(movie_cast,my_api_key) {
    var cast_bdays = [];
    var cast_bios = [];
    var cast_places = [];
    for(var cast_id in movie_cast.cast_ids){
      $.ajax({
        type:'GET',
        url:'https://api.themoviedb.org/3/person/'+movie_cast.cast_ids[cast_id]+'?api_key='+my_api_key,
        async:false,
        success: function(cast_details){
          if(cast_details.birthday){
             cast_bdays.push((new Date(cast_details.birthday)).toDateString().split(' ').slice(1).join(' '));
          } else {
             cast_bdays.push("Not Available");
          }
          if(cast_details.biography){
              var cleanBio = cast_details.biography.replace(/"/g, "'").replace(/\n/g, " ");
              cast_bios.push(cleanBio);
          } else {
              cast_bios.push("No biography available.");
          }
          if(cast_details.place_of_birth){
              cast_places.push(cast_details.place_of_birth);
          } else {
              cast_places.push("Not Available");
          }
        }
      });
    }
    return {cast_bdays:cast_bdays,cast_bios:cast_bios,cast_places:cast_places};
}

function get_movie_cast(movie_id,my_api_key){
    var cast_ids= [];
    var cast_names = [];
    var cast_chars = [];
    var cast_profiles = [];
    var top_cast = [];

    $.ajax({
      type:'GET',
      url:"https://api.themoviedb.org/3/movie/"+movie_id+"/credits?api_key="+my_api_key,
      async:false,
      success: function(my_movie){
        if(my_movie.cast.length>=10){
          top_cast = [0,1,2,3,4,5,6,7,8,9];
        }
        else {
          for(var i=0; i<my_movie.cast.length; i++) top_cast.push(i);
        }
        for(var my_cast in top_cast){
          cast_ids.push(my_movie.cast[my_cast].id)
          cast_names.push(my_movie.cast[my_cast].name);
          cast_chars.push(my_movie.cast[my_cast].character);

          if(my_movie.cast[my_cast].profile_path){
              cast_profiles.push("https://image.tmdb.org/t/p/original"+my_movie.cast[my_cast].profile_path);
          } else {
              cast_profiles.push("https://placehold.co/300x450?text=No+Photo");
          }
        }
      },
      error: function(){
        alert("Invalid Request!");
        $("#loader").delay(500).fadeOut();
      }
    });

    return {cast_ids:cast_ids,cast_names:cast_names,cast_chars:cast_chars,cast_profiles:cast_profiles};
}

function get_movie_posters(arr,my_api_key){
  var arr_poster_list = []
  for(var m in arr) {
    $.ajax({
      type:'GET',
      url:'https://api.themoviedb.org/3/search/movie?api_key='+my_api_key+'&query='+arr[m],
      async: false,
      success: function(m_data){
        if (m_data.results.length > 0 && m_data.results[0].poster_path) {
            arr_poster_list.push('https://image.tmdb.org/t/p/original'+m_data.results[0].poster_path);
        } else {
            arr_poster_list.push('https://placehold.co/500x750?text=No+Image');
        }
      },
      error: function(){
        alert("Invalid Request!");
        $("#loader").delay(500).fadeOut();
      },
    })
  }
  return arr_poster_list;
}

/* --- HANDLE LIKE & SAVE BUTTON CLICKS --- */
function toggleAction(btn, action, movieId, title, poster) {
    // 1. Visually toggle immediately (Instant Feedback)
    if (action === 'like') {
        $(btn).toggleClass('liked');

        // Optional: Change icon from 'favorite_border' to 'favorite' (Filled Heart)
        var icon = $(btn).find('i');
        if ($(btn).hasClass('liked')) {
            icon.text('favorite');
        } else {
            icon.text('favorite_border');
        }
    }
    else if (action === 'save') {
        $(btn).toggleClass('saved');

        // Optional: Change icon from 'bookmark_border' to 'bookmark' (Filled Bookmark)
        var icon = $(btn).find('i');
        if ($(btn).hasClass('saved')) {
            icon.text('bookmark');
        } else {
            icon.text('bookmark_border');
        }
    }

    // 2. Send data to Python Backend (Background)
    $.ajax({
        url: "/toggle_action",
        type: "POST",
        contentType: "application/json",
        data: JSON.stringify({
            "action": action,
            "movie_id": movieId,
            "title": title,
            "poster": poster
        }),
        success: function(response) {
            console.log("Action saved:", response.status);
        },
        error: function(err) {
            console.log("Error saving action");
            // Revert visual change if server fails
            if(action === 'like') $(btn).toggleClass('liked');
            if(action === 'save') $(btn).toggleClass('saved');
        }
    });
}
/* --- CHATBOT LOGIC (With Session Memory) --- */
$(document).ready(function() {

    // 1. Load History when page opens
    loadChatHistory();

    // Open Chat
    $("#chat-circle").click(function() {
      $("#chat-circle").fadeOut(200);
      $(".chat-box").fadeIn(300);
      // Scroll to bottom when opening
      $(".chat-logs").scrollTop($(".chat-logs")[0].scrollHeight);
    });

    // Close Chat
    $(".chat-box-toggle").click(function() {
      $(".chat-box").fadeOut(200);
      $("#chat-circle").fadeIn(300);
    });

    // Send Message
    $("#chat-submit").click(function(e) {
      e.preventDefault();
      var msg = $("#chat-input").val();
      if(msg.trim() == ''){ return false; }

      generate_message(msg, 'user');

      // AJAX Call to Python Backend
      $.ajax({
        url: "/chat",
        type: "POST",
        contentType: "application/json",
        data: JSON.stringify({ "message": msg }),
        success: function(response) {
            generate_message(response.response, 'bot');
        },
        error: function() {
            generate_message("My brain is offline (Check Flask Console).", 'bot');
        }
      });
    });

    // --- HELPER FUNCTIONS ---

    // 1. Render HTML & Save to Memory
    function generate_message(msg, type) {
      // Render to screen
      render_message_html(msg, type);

      // Save to Session Storage
      var history = JSON.parse(sessionStorage.getItem("chat_history")) || [];
      history.push({ msg: msg, type: type });
      sessionStorage.setItem("chat_history", JSON.stringify(history));

      // Clear input & Scroll
      $("#chat-input").val('');
      $(".chat-logs").stop().animate({ scrollTop: $(".chat-logs")[0].scrollHeight}, 1000);
    }

    // 2. Just Render HTML (Don't save again)
    function render_message_html(msg, type) {
      var str = "";
      str += "<div class='chat-msg "+type+"'>";
      str += "<span class='cm-msg-text'>"+msg+"</span>";
      str += "</div>";
      $(".chat-logs").append(str);
    }

    // 3. Load from Memory
    function loadChatHistory() {
        var history = JSON.parse(sessionStorage.getItem("chat_history")) || [];

        // If we have history, clear the default "Hi!" message and load real chat
        if (history.length > 0) {
            $(".chat-logs").empty(); // Remove default greeting
            history.forEach(function(item) {
                render_message_html(item.msg, item.type);
            });
            // Scroll to bottom immediately
            $(".chat-logs").scrollTop($(".chat-logs")[0].scrollHeight);
        }
    }

});
// End of Chatbot Logic