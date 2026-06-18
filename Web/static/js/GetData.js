
// async function sendGETRequest() {

//     const approximateNanoseconds = BigInt(Date.now()) * 1000000n;
//     // const baseUrl = `http://127.0.0.1:3000/drt2/${approximateNanoseconds}`;
//     const baseUrl = `http://127.0.0.1:3000/drt2/1773421402570729600`;

//     const url = new URL(baseUrl);

//     fetch(url)
//     .then(response => response.json())
//     .then(data => {
//         // console.log(data);
//         return data;
//     })
//     .catch(error => {
//         console.error('Error fetching data:', error);
//     });
// }


async function sendGETRequest() {
    const baseUrl = `http://192.168.86.250:3000/drt2/1773421402570729600`;
    const url = new URL(baseUrl);

    try {
        const response = await fetch(url);
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error fetching data:', error);
    }
}