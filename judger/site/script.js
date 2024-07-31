"use strict"

let divs = []

let timetable_body = document.querySelector ('#timetable_body')
for (let i = 0; i < 6; i++) {
    let tr = document.createElement ('tr')
    tr.classList.add ('timetable_row')
    divs.push([])
    for (let j = 0; j < 5; j++) {
        let td = document.createElement ('td')
        let div = document.createElement ('div')
        divs[divs.length-1].push(div)
        td.appendChild (div)
        tr.appendChild (td)
    }
    timetable_body.appendChild (tr)
}

let pages = []

for (let subject in data) {
    for (let type in data[subject]) {
        pages.push([subject, type])
    }
}

let badness = {}
for (let subject in data) {
    badness[subject] = {}
    for (let type in data[subject]) {
        badness[subject][type] = {}
        for (let group in data[subject][type]) {
            badness[subject][type][group] = 0
        }
    }
}

let days_to_indices = {'poniedziałek': 0, 'wtorek': 1, 'środa': 2, 'czwartek': 3, 'piątek': 4}

let subject_data = document.querySelector('#subject_data')
let badness_slider = document.querySelector('#badness_slider')

let currently_displayed_entries = []
let current_active_group = null
let current_subject = null
let current_type = null

let map_group_names_to_divs = {}

badness_slider.addEventListener("input", (event) => {
    if (current_active_group == null) {
        return;
    }
    badness[current_subject][current_type][current_active_group] = event.target.value;
    console.log ('here')
    for (let div of map_group_names_to_divs[current_active_group]) {
        console.log ('in for')
        div.style = `background-color: color-mix(in srgb, green, red ${event.target.value * 10}%);`
    }
  });

function display_page (page_num) {

    current_active_group = null
    map_group_names_to_divs = {}

    for (let entry of currently_displayed_entries) {
        entry.remove()
    }

    console.log ('displaying page', page_num)
    current_subject = pages[page_num][0]
    current_type = pages[page_num][1]
    subject_data.textContent = current_subject + ' ' + current_type

    let current_subject_group_map = data[pages[page_num][0]][pages[page_num][1]]
    for (let group_name in current_subject_group_map) {

        for (let hour of current_subject_group_map[group_name]) {
            let lesson = hour['lesson']
            console.log ('lesson', lesson)
    
            let day = days_to_indices[hour['day']]

            let whole_div = document.createElement ('div')
            whole_div.classList.add ('timetable_entry')
            let group_span = document.createElement ('span')
            group_span.textContent = `grupa: ${group_name}`
            whole_div.appendChild (group_span)
            let teacher_span = document.createElement ('span')
            teacher_span.textContent = `prowadzący: ${hour['teacher']}`
            whole_div.appendChild (teacher_span)

            let current_badness = badness[current_subject][current_type][group_name]
            whole_div.style = `background-color: color-mix(in srgb, green, red ${current_badness * 10}%);`

            whole_div.addEventListener ('click', function () {
                current_active_group = group_name
                badness_slider['value'] = badness[current_subject][current_type][group_name]
            })

            map_group_names_to_divs[group_name] ||= []
            map_group_names_to_divs[group_name].push (whole_div)

            currently_displayed_entries.push (whole_div)
    
            divs[lesson][day].appendChild (whole_div)
    
            console.log (current_subject_group_map[group_name])
        }
        
    }
}

let page_buttons_div = document.querySelector ('#page_buttons')

for (let i = 0; i < pages.length; i++) {
    let button = document.createElement ('button')
    button.textContent = i
    button.addEventListener ('click', function () {display_page(i)})
    page_buttons_div.appendChild (button)
}

display_page (0)

function download_data(uri, name) {
    let link = document.createElement("a");
    link.download = name;
    link.href = uri;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    link.remove()
  }

let download_button = document.createElement ('button')
download_button.textContent = "DOWNLOAD"
download_button.addEventListener ('click', function () {
    download_data ('data:text/json,' + JSON.stringify (badness), 'data.json')
})
document.body.appendChild (download_button)