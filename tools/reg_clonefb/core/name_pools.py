# -*- coding: utf-8 -*-
"""
core.name_pools
Kho du lieu ho ten cuc lon va da dang da quoc gia cho Facebook Registration Tool.
Bao gom 12 quoc gia va khu vuc: Viet Nam, Tay, An Do, Thai Lan, Trung Quoc, Han Quoc, Nhat Ban, v.v.
"""

DEM_NAM_VIET = [
    'Quốc', 'Văn', 'Minh', 'Đức', 'Hoàng', 'Gia', 'Hải', 'Tuấn', 'Thanh', 'Hữu',
    'Xuân', 'Thành', 'Bảo', 'Đình', 'Công', 'Trọng', 'Duy', 'Mạnh', 'Phúc', 'Tấn',
    'Quang', 'Đăng', 'Khắc', 'Ngọc', 'Tiến', 'Anh', 'Vĩnh', 'Thái', 'Hồng', 'Kim',
    'Hạo', 'Chí', 'Vũ', 'Bách', 'Đạt', 'Trí', 'Trực', 'Nam', 'Phong', 'Khang',
    'Lâm', 'Triết', 'Nguyên', 'Thiện', 'Trường', 'Quân', 'Bình', 'Kiên', 'Long', 'Tuệ',
    'An', 'Nhật', 'Trung', 'Hiệp', 'Lộc', 'Khoa', 'Hiển', 'Cảnh', 'Định', 'Kiệt',
    'Toàn', 'Cương', 'Huân', 'Tường', 'Vỹ', 'Phi', 'Thắng', 'Đông', 'Tân', 'Huy',
    'Phát', 'Thịnh', 'Cường', 'Sơn', 'Tùng', 'Tài', 'Vinh', 'Hùng', 'Triệu', 'Việt',
    'Nghĩa', 'Nhân', 'Phương', 'Giang', 'Bắc', 'Thuận', 'Hiền', 'Hoài', 'Chính', 'Thiên',
    'Lạc', 'Vĩ', 'Khải', 'Viễn', 'Phước', 'Cao', 'Chấn', 'Đan', 'Đoan', 'Hậu',
    'Hiếu', 'Kha', 'Khánh', 'Khiêm', 'Khôi'
]

DEM_NU_VIET = [
    'Thị', 'Ngọc', 'Thu', 'Thanh', 'Phương', 'Kim', 'Quỳnh', 'Ánh', 'Mỹ', 'Mai',
    'Hồng', 'Tuyết', 'Bích', 'Như', 'Diễm', 'Cẩm', 'Yến', 'Thảo', 'Hương', 'Khánh',
    'Thùy', 'Băng', 'Trúc', 'Hà', 'Cát', 'Bảo', 'Tú', 'Thục', 'Minh', 'Gia',
    'Hạ', 'Lan', 'Hoài', 'Xuân', 'Nhã', 'Tâm', 'Uyên', 'An', 'Lệ', 'Huyền',
    'Trang', 'Thúy', 'Vân', 'Ngân', 'Linh', 'Hạnh', 'Kiều', 'Trâm', 'Đoan', 'Diệu',
    'Nga', 'Thi', 'Duyên', 'Khuê', 'Bội', 'Loan', 'Mộng', 'Tường', 'Hải', 'Ly',
    'Diệp', 'Ái', 'Chi', 'Dung', 'Dạ', 'Đan', 'Giang', 'Hảo', 'Hằng', 'Hân',
    'Hiền', 'Hoa', 'Hoàng', 'Huệ', 'Hường', 'Khả', 'Lam', 'Liễu', 'Mi', 'My',
    'Nghi', 'Nguyệt', 'Nhi', 'Nhung', 'Oanh', 'Phượng', 'Phúc', 'Quế', 'Quyên', 'San',
    'Sương', 'Tố', 'Trân', 'Triều', 'Vàng', 'Vy', 'Xuyến', 'Ý', 'Lài'
]

FIRST_NAMES_FEMALE_ARABIC = [
    'Fatima', 'Aisha', 'Maryam', 'Noor', 'Sarah', 'Layla', 'Zainab', 'Salma', 'Reem', 'Huda',
    'Rana', 'Dana', 'Yasmin', 'Rania', 'Mona', 'Lina', 'Maya', 'Hana', 'Malak', 'Farah',
    'Tala', 'Judy', 'Samar', 'Amira', 'Bayan', 'Dina', 'Ghada', 'Habiba', 'Inas', 'Jana',
    'Karma', 'Layan', 'Marwa', 'Nada', 'Ola', 'Rawan', 'Sahar', 'Tamara', 'Wafa', 'Yara',
    'Zahra', 'Asma', 'Basma', 'Dalal', 'Faten', 'Halima', 'Iman', 'Jumana', 'Khulood', 'Lubna',
    'Abeer', 'Bushra', 'Dalia', 'Fadwa', 'Ghina', 'Hala', 'Israa', 'Jawaher', 'Khadija', 'Lamis',
    'Manal', 'Najwa', 'Omnia', 'Qamar', 'Ruba', 'Shatha', 'Tasneem', 'Ula', 'Widad', 'Yusra',
    'Afaf', 'Badia', 'Dareen', 'Fayza', 'Ghalia', 'Hanan', 'Ibtisam', 'Jihan', 'Kawkab', 'Laila', 'Aaliyah',
    'Amina', 'Ayah', 'Aziza', 'Hafsa', 'Hoda', 'Jamilah', 'Joud', 'Lama', 'Leen', 'Maha',
    'Mariam', 'May', 'Munira', 'Nabila', 'Nadia', 'Nadine', 'Noura', 'Sara', 'Aya', 'Hiba',
    'Lamia', 'Samira', 'Tahira', 'Isra', 'Nawal', 'Abla', 'Afifa', 'Ahlam', 'Aida', 'Alia',
    'Almas', 'Amal', 'Amani', 'Amatullah', 'Amber', 'Aminah', 'Anan', 'Anbar', 'Anisa', 'Ansam',
    'Areej', 'Arwa', 'Aseel', 'Asiya', 'Athir', 'Atifa', 'Atiyya', 'Azhar', 'Badra', 'Bahia',
    'Bahira', 'Bahiya', 'Balqis', 'Ban', 'Baraka', 'Bashira', 'Basima', 'Batool', 'Bilqis', 'Budur',
    'Buthaina', 'Chaza', 'Dania', 'Deema', 'Dima', 'Duha', 'Fadila', 'Fahima', 'Faiza', 'Falak',
    'Farida', 'Fariha', 'Fatin', 'Fawziya', 'Fayha', 'Fayruz', 'Firdaus', 'Ghaida', 'Ghaliya', 'Ghania',
    'Ghazal', 'Hadeel', 'Hadia', 'Hagar', 'Haifa'
]

FIRST_NAMES_FEMALE_BRAZILIAN = [
    'Julia', 'Beatriz', 'Larissa', 'Mariana', 'Camila', 'Amanda', 'Leticia', 'Bruna', 'Jessica', 'Carolina',
    'Fernanda', 'Luana', 'Gabriela', 'Nathalia', 'Juliana', 'Bianca', 'Rebeca', 'Alice', 'Sophia', 'Helena',
    'Valentina', 'Laura', 'Manuela', 'Isabella', 'Heloisa', 'Luiza', 'Lorena', 'Livia', 'Giovanna', 'Maria',
    'Cecilia', 'Eloah', 'Mirella', 'Emanuelly', 'Isadora', 'Ana', 'Rafaela', 'Yasmin', 'Patricia', 'Aline',
    'Vanessa', 'Tatiane', 'Renata', 'Simone', 'Priscila', 'Debora', 'Flavia', 'Cintia', 'Daniela', 'Elaine',
    'Agatha', 'Barbara', 'Clarisse', 'Danielly', 'Eduarda', 'Fatima', 'Gisele', 'Ingrid', 'Joana', 'Kelly',
    'Ligia', 'Marcela', 'Nayara', 'Olivia', 'Paloma', 'Raquel', 'Sabrina', 'Talita', 'Viviane', 'Adriana',
    'Brenda', 'Carla', 'Diana', 'Ester', 'Franciele', 'Graziela', 'Heidi', 'Iara', 'Jacqueline', 'Karina',
    'Luciana', 'Marta', 'Nubia', 'Olga', 'Perla', 'Rita', 'Silvia', 'Tereza', 'Veronica', 'Alana',
    'Maitê', 'Liz', 'Lara', 'Antonella', 'Melissa', 'Clara', 'Marina', 'Sarah', 'Emanuelle', 'Isabelly',
    'Lavinia', 'Nicole', 'Abadia', 'Abigail', 'Acacia', 'Ada', 'Adalgisa', 'Adalia', 'Adelaide', 'Adelia',
    'Adelina', 'Adelita', 'Adriane', 'Agda', 'Aglaia', 'Agnes', 'Agostinha', 'Agripina', 'Aida', 'Aila',
    'Aimee', 'Aisha', 'Alaide', 'Alba', 'Albana', 'Albertina', 'Albina', 'Alcione', 'Alcira', 'Alda',
    'Aldegunda', 'Aldenora', 'Alecsandra', 'Alegria', 'Alejandra', 'Alessandra', 'Alexia', 'Alicia', 'Alina', 'Almerinda',
    'Almira', 'Aloisia', 'Altina', 'Alva', 'Alvair', 'Alvina', 'Alzira', 'Amabile', 'Amalia', 'Amandina',
    'Amara', 'Amarilis', 'Amelia', 'Amelina', 'America', 'Amerinda', 'Amira', 'Anabel', 'Anabela', 'Anaide',
    'Anair', 'Analia', 'Ananias', 'Anastacia', 'Anatolia', 'Andrea', 'Andreia', 'Andreina', 'Andressa', 'Andria',
    'Anelise', 'Anete', 'Angela', 'Angelica', 'Angelina', 'Angelita', 'Anita', 'Anizia', 'Anna', 'Annamaria',
    'Antonia', 'Antonina', 'Aparecida', 'Apolonia', 'Araci', 'Araceli', 'Ariana', 'Ariane', 'Ariele', 'Ariene',
    'Arinda', 'Arlete', 'Arminda', 'Atenas', 'Audrey', 'Aura'
]

FIRST_NAMES_FEMALE_CHINESE = [
    'Jing', 'Fang', 'Na', 'Li', 'Min', 'Yan', 'Ting', 'Juan', 'Xiu', 'Ying',
    'Mei', 'Ping', 'Hong', 'Ling', 'Xia', 'Yu', 'Dan', 'Fen', 'Lan', 'Qian',
    'Hui', 'Yun', 'Qiao', 'Meng', 'Xin', 'Rou', 'Yue', 'Jia', 'Lu', 'Huan',
    'Shuang', 'Fei', 'Rong', 'Chun', 'Zhen', 'Rui', 'Shan', 'Han', 'Ni', 'Wen',
    'Xuan', 'Chen', 'Lin', 'Qing', 'Yao', 'Ya', 'Zhu', 'Wei', 'Xi', 'Yutong',
    'Xinyi', 'Yinuo', 'Zihan', 'Yuxin', 'Mengjie', 'Ruoxi', 'Shihan', 'Jiayi', 'Yiting', 'Ziyan',
    'Xinyue', 'Ruotong', 'Chenxi', 'Tingting', 'Xiaohan', 'Zhihan', 'Yujia', 'Shiyao', 'Haoyu', 'Linglong',
    'Kexin', 'Yifei', 'Nuoyan', 'Yutang', 'Mingrui', 'Jiaxin', 'Yuqing', 'Wanqing', 'Siyuan', 'Xinya',
    'Ruolin', 'Yixuan', 'Yuehan', 'Jingya', 'Meihua', 'Xiaoyu', 'Wenjing', 'Lihua', 'Haiyan', 'Guiying',
    'Xiuying', 'Yulan', 'Shufen', 'Fengying', 'Xue', 'Xiaohong', 'Xiaoyan', 'Lijuan', 'Ailing', 'Baoyu',
    'Chuyue', 'Danfeng', 'Enxi', 'Fanghua', 'Guanying', 'Haixia', 'Jiayue', 'Kexuan', 'Linyue', 'Mengyao',
    'Ningjing', 'Peishan', 'Qingwen', 'Ruoqing', 'Shuying', 'Tianying', 'Wenxi', 'Xiaoxiao', 'Yanzhi', 'Zixuan',
    'Anqi', 'Bingqing', 'Cailin', 'Dongyue', 'Fangfei', 'Guilan', 'Hanyu', 'Jialing', 'Kaili', 'Lingling',
    'Meilin', 'Ningning', 'Peipei', 'Qiuling', 'Ronghua', 'Shuangshuang', 'Tongtong', 'Wenxin', 'Xiaomeng', 'Yiyi',
    'Zhenzhen', 'Aijia', 'Biqing', 'Chunhua', 'Danni', 'Feiyan', 'Guanlan', 'Huanhuan', 'Jiamin', 'Kongying',
    'Ai', 'Aihua', 'Aijun', 'Aimin', 'An', 'Anan', 'Baohua', 'Beibei', 'Bi', 'Bing',
    'Bingbing', 'Bingjie', 'Bo', 'Cai', 'Caixia', 'Can', 'Chai', 'Chang', 'Chao', 'Chenchen',
    'Chu', 'Chunfang', 'Chunjuan', 'Chunli', 'Chunlian', 'Chunmei', 'Chunrong', 'Chunxia', 'Chunyan', 'Ci',
    'Cong', 'Cui', 'Cuicui', 'Cuifang', 'Cuihua', 'Cuilian', 'Cuimei', 'Cuiping', 'Cuixia', 'Cuiyan',
    'Da', 'Dandan', 'Danping', 'De', 'Di', 'Dia', 'Dian', 'Dong', 'Dongfang', 'Dongmei',
    'Dongxue', 'En', 'Er', 'Fa', 'Fan', 'Fangfang', 'Fangjuan', 'Fangli', 'Fanglian', 'Fangmei',
    'Fangping', 'Fangrong', 'Fangting', 'Fangwei', 'Fangxia', 'Fangyan', 'Fangyi', 'Fangyu', 'Feifei', 'Fenfang',
    'Feng', 'Fenghua', 'Fengjuan', 'Fenglan', 'Fengli', 'Guifang', 'Guihua', 'Guilian', 'Guimei', 'Guiping',
    'Guixia', 'Bao', 'Die', 'Ge', 'Guan', 'Hao', 'He', 'Hongmei', 'Hongxia', 'Hongyan', 'Hua',
    'Huifen', 'Huiling', 'Huimin', 'Jiahui', 'Jiali', 'Jian', 'Jiang', 'Jiao', 'Jie', 'Jin',
    'Jinghua', 'Jingjing', 'Jingyi', 'Juanjuan', 'Jue', 'Jun', 'Ke', 'Lanfang', 'Le', 'Lei',
    'Lian', 'Liang', 'Lili', 'Liu', 'Luan', 'Man', 'Meifeng', 'Meiling', 'Meirong', 'Miao',
    'Yuting', 'Ruohan', 'Xintong', 'Shuhan', 'Yuxuan', 'Yihan', 'Wenxuan', 'Yingying', 'Siyi', 'Meiqi',
    'Xirui', 'Yichen', 'Xinyan', 'Ruirui', 'Peixin', 'Yuteng', 'Nuoxi', 'Zhirui', 'Lingxi', 'Sihan',
    'Tingxuan', 'Yingxuan', 'Qianqian'
]

FIRST_NAMES_FEMALE_FILIPINO = [
    'Angel', 'Bea', 'Christine', 'Nicole', 'Mary', 'Princess', 'Sarah', 'Kathryn', 'Liza', 'Marian',
    'Heart', 'Nadine', 'Maine', 'Andrea', 'Bianca', 'Camille', 'Danica', 'Erika', 'Francine', 'Gladys',
    'Hazel', 'Ivy', 'Joyce', 'Karen', 'Lorna', 'Maricel', 'Nenita', 'Ofelia', 'Perla', 'Queenie',
    'Rowena', 'Sharon', 'Tessie', 'Ursula', 'Vilma', 'Winona', 'Xandra', 'Yvette', 'Zenaida', 'Alma',
    'Bernadette', 'Carla', 'Darna', 'Elaine', 'Fe', 'Gemma', 'Honey', 'Imelda', 'Jocelyn', 'Kris',
    'Althea', 'Patricia', 'Jasmine', 'Mikaela', 'Janella', 'Kimberly', 'Rhea', 'Trisha', 'Alyssa', 'Danielle',
    'Francesca', 'Giselle', 'Ina', 'Lorraine', 'Nikki', 'Ophelia', 'Paula', 'Roxanne', 'Shiela', 'Tanya',
    'Vanessa', 'Wendy', 'Ysabel', 'Amalia', 'Corazon', 'Divina', 'Esperanza', 'Gloria', 'Honoria', 'Jacinta',
    'Katarina', 'Leonora', 'Milagros', 'Natividad', 'Perlita', 'Rosario', 'Soledad', 'Teresita', 'Abigail', 'Ada',
    'Adela', 'Adelaida', 'Adelina', 'Adriana', 'Agatha', 'Agnes', 'Agustina', 'Aida', 'Aileen', 'Aimee',
    'Alba', 'Alberta', 'Albertina', 'Alejandra', 'Alena', 'Alexia', 'Alexis', 'Alfonsa', 'Alfreda', 'Alicia',
    'Alina', 'Almira', 'Aloha', 'Amada', 'Amanda', 'Amelia', 'Amor', 'Amparo', 'Ana', 'Anabel',
    'Anastacia', 'Anatalia', 'Andeng', 'Angela', 'Angelica', 'Angelina', 'Angie', 'Anita', 'Ann', 'Anna',
    'Annaliza', 'Antonia', 'Antonina', 'Anunciacion', 'Apolonia', 'Araceli', 'Arlene', 'Armida', 'Asuncion', 'Aubrey',
    'Audrey', 'Augusta', 'Aurea', 'Aurelia', 'Aurora', 'Ave', 'Avelina', 'Ayra', 'Azucena', 'Balbina',
    'Barbara', 'Basilia', 'Beatriz', 'Belen', 'Belinda', 'Benedicta', 'Benigna', 'Benita', 'Bernadeth', 'Bernarda',
    'Bernardita', 'Berta', 'Bibiana', 'Bienvenida', 'Blanca', 'Blesilda', 'Bonifacia', 'Brenda', 'Brigida', 'Buenaventurada',
    'Candida', 'Caridad', 'Carina', 'Carlota', 'Carmela', 'Carmelita', 'Carmen', 'Carmina', 'Carolina', 'Casiana',
    'Catalina', 'Cecilia', 'Celerina'
]

FIRST_NAMES_FEMALE_INDIAN = [
    'Aadhya', 'Saanvi', 'Ananya', 'Diya', 'Kiara', 'Pari', 'Myra', 'Anvi', 'Riya', 'Prisha',
    'Aanya', 'Isha', 'Ahana', 'Anika', 'Avani', 'Siya', 'Navya', 'Sara', 'Shanaya', 'Kavya',
    'Priya', 'Sneha', 'Pooja', 'Neha', 'Ritu', 'Swati', 'Shweta', 'Divya', 'Megha', 'Payal',
    'Komal', 'Kajal', 'Nisha', 'Jyoti', 'Anjali', 'Suman', 'Sunita', 'Rekha', 'Anita', 'Geeta',
    'Poonam', 'Preeti', 'Simran', 'Aarti', 'Archana', 'Barkha', 'Chetna', 'Deepa', 'Garima', 'Hemlata',
    'Indu', 'Jaya', 'Karuna', 'Lalita', 'Mamta', 'Namrata', 'Pallavi', 'Rachna', 'Sadhana', 'Tanu',
    'Urmila', 'Vandana', 'Yamini', 'Aastha', 'Bhavna', 'Charu', 'Drishti', 'Ekta', 'Gunjan', 'Harshita',
    'Ishita', 'Juhi', 'Kriti', 'Lavanya', 'Mansi', 'Nandini', 'Palak', 'Radhika', 'Sakshi', 'Tanya',
    'Urvashi', 'Vidhi', 'Yashika', 'Aditi', 'Anushka', 'Disha', 'Gauri', 'Janhvi', 'Khushi', 'Mahika',
    'Nidhi', 'Parineeti', 'Richa', 'Samaira', 'Tara', 'Vanya', 'Zara', 'Alisha', 'Fatima', 'Sania',
    'Heena', 'Yasmin', 'Ayesha', 'Muskan', 'Amita', 'Anamika', 'Ankita', 'Anshika', 'Arpita', 'Ashwini',
    'Babita', 'Chandana', 'Chhaya', 'Damini', 'Deeksha', 'Deepali', 'Deepshikha', 'Dipti', 'Gargi', 'Gayatri',
    'Hema', 'Himani', 'Ila', 'Indira', 'Jalpa', 'Janki', 'Jaspreet', 'Kalyani', 'Kamini', 'Kanchan',
    'Kiran', 'Kirti', 'Kumud', 'Lata', 'Leela', 'Madhu', 'Madhuri', 'Malini', 'Manju', 'Meenakshi',
    'Mridula', 'Mukta', 'Nalini', 'Neelam', 'Nirupama', 'Padma', 'Padmini', 'Pratibha', 'Pushpa', 'Ragini',
    'Rajni', 'Rani', 'Rashmi', 'Ratna', 'Renuka', 'Roshni', 'Rupali', 'Sandhya', 'Sangeeta', 'Sarita',
    'Saroj', 'Seema', 'Shalu', 'Shanta', 'Shashi', 'Shobha', 'Shraddha', 'Shreya', 'Smita', 'Sudha',
    'Sujata', 'Sulochana', 'Sunaina', 'Sushma', 'Tanushree', 'Trisha', 'Uma', 'Usha', 'Vaidehi', 'Anaya',
    'Ira', 'Deepika', 'Esha', 'Ishika', 'Meera', 'Priyanka', 'Radha', 'Rashi', 'Tanvi', 'Shilpa',
    'Tulsi', 'Yamuna', 'Bhumika', 'Chhavi', 'Harini', 'Ishani', 'Janhavi', 'Kritika', 'Laxmi', 'Prerna',
    'Varsha', 'Aanchal', 'Bina', 'Chanda', 'Geetika', 'Naveli', 'Pranjal', 'Riddhima', 'Sanjana', 'Zoya',
    'Aarohi', 'Alankrita', 'Amrita', 'Aparna', 'Aradhana', 'Archita', 'Arundhati', 'Asmita', 'Avantika', 'Bhagyashree',
    'Chaitali', 'Darshana', 'Devika', 'Dolly', 'Haimi', 'Hansa', 'Harshada', 'Jagriti', 'Jayanti', 'Jhanvi',
    'Joshita', 'Kalpana', 'Kanchana', 'Kanika', 'Kashish', 'Kasturi', 'Keerthi', 'Kinjal', 'Krithika', 'Kusuma',
    'Lipi', 'Madhavi', 'Mallika', 'Manisha', 'Manjari', 'Manorama', 'Medha', 'Menaka', 'Mithila', 'Mohini',
    'Monalisa', 'Naina', 'Narmada', 'Nikita', 'Nimisha', 'Nishi', 'Nupur', 'Oindrila', 'Padmaja', 'Parul',
    'Pavithra', 'Payelia', 'Poornima', 'Prachi', 'Pragati', 'Pragya', 'Pranati', 'Rajani', 'Rajshree', 'Rakhi',
    'Reena', 'Riddhi', 'Rimjhim', 'Rohini', 'Ruchi', 'Rupal', 'Sabita', 'Sahana', 'Samiksha', 'Sampada',
    'Sanvi', 'Sarala', 'Shalini', 'Shamita', 'Shanti', 'Sharanya', 'Sharmila', 'Sheela', 'Shikha', 'Shipra',
    'Shivangi', 'Shivani', 'Shubhangi', 'Smriti', 'Snehlata', 'Sonali', 'Sonam', 'Soniya', 'Srishti', 'Subhadra',
    'Suchitra', 'Sukanya', 'Sulabha', 'Sumanlata', 'Supriya', 'Surabhi', 'Sushila', 'Sushmita', 'Swaroopa', 'Tanuja',
    'Tejaswi', 'Trupti', 'Upasana', 'Vaishali', 'Vasudha', 'Vedika', 'Vibha', 'Vijaya', 'Vimala', 'Vineeta',
    'Vrinda', 'Akanksha', 'Amisha', 'Devi', 'Divyani', 'Aadriti', 'Aakanksha', 'Aaradhya', 'Aarna', 'Aathira', 'Abha',
    'Abhilasha', 'Advika', 'Aishani', 'Aishwarya', 'Alka', 'Ambika', 'Anagha', 'Anandi', 'Anisha', 'Anju',
    'Anupama', 'Anusha', 'Aparajita', 'Ayushi', 'Barnali', 'Basanti', 'Bela', 'Bhagyalakshmi', 'Bhairavi', 'Bhanupriya',
    'Bharati', 'Bhavana', 'Bhavika', 'Bhoomika', 'Bijoya', 'Chaitra', 'Chanchal', 'Chandini', 'Chandrika', 'Chitra',
    'Damayanti', 'Deepti', 'Devashree', 'Dhanya', 'Dharini', 'Dharti', 'Divyata', 'Gaura', 'Geetanjali', 'Girija',
    'Gowri', 'Grishma', 'Hamsini', 'Harshali', 'Hemali', 'Sia', 'Mahi', 'Nyra', 'Pihu', 'Keya',
    'Arya', 'Bhavya', 'Natasha', 'Rhea', 'Alia', 'Ruhi'
]

FIRST_NAMES_FEMALE_INDONESIAN = [
    'Sari', 'Putri', 'Dewi', 'Siti', 'Nur', 'Indah', 'Ratna', 'Maya', 'Rini', 'Tri',
    'Wulan', 'Anita', 'Desi', 'Dian', 'Fitri', 'Gita', 'Ayu', 'Melati', 'Nanda', 'Rina',
    'Tari', 'Utami', 'Winda', 'Yuni', 'Anisa', 'Nadia', 'Lestari', 'Mega', 'Novita', 'Anggi',
    'Bella', 'Citra', 'Dina', 'Erna', 'Febri', 'Grace', 'Hani', 'Intan', 'Juwita', 'Kartika',
    'Laras', 'Mawar', 'Nia', 'Okta', 'Puspa', 'Ratih', 'Siska', 'Tiara', 'Ulfa', 'Vina',
    'Widya', 'Yanti', 'Zahra', 'Aulia', 'Bunga', 'Cantika', 'Devi', 'Elisa', 'Fani', 'Gisella',
    'Hilda', 'Ika', 'Jessica', 'Karin', 'Linda', 'Mira', 'Neneng', 'Olla', 'Pratiwi', 'Rika',
    'Sri', 'Dinda', 'Nadya', 'Yulia', 'Adinda', 'Agustina', 'Aisyah', 'Amalia', 'Amanda', 'Amira', 'Ananda',
    'Anggun', 'Annisa', 'Aprillia', 'Arum', 'Damayanti', 'Diah', 'Dwi', 'Endang', 'Fadilah', 'Farida',
    'Halimah', 'Hana', 'Hartati', 'Hasanah', 'Hastuti', 'Herlina', 'Hesti', 'Kusuma', 'Mirna', 'Wulandari',
    'Endah', 'Jelita', 'Novi', 'Permata', 'Rani', 'Ade', 'Adel', 'Adelia', 'Adinda', 'Agatha',
    'Agnes', 'Aida', 'Ajeng', 'Alda', 'Alfi', 'Alfiana', 'Alia', 'Alika', 'Alina', 'Alisa',
    'Allya', 'Alma', 'Almira', 'Alviana', 'Amelia', 'Ana', 'Anastasia', 'Andi', 'Andina', 'Andini',
    'Angela', 'Anggia', 'Anggie', 'Anggraini', 'Anis', 'Anissa', 'April', 'Aprilia', 'Ardita', 'Ari',
    'Ariana', 'Ariani', 'Arie', 'Arika', 'Arina', 'Arini', 'Arisandi', 'Ariska', 'Ariyanti', 'Armi',
    'Arya', 'Asih', 'Asri', 'Astrid', 'Astuti', 'Aurelia', 'Aurell', 'Ayunda', 'Azizah', 'Bela',
    'Bening', 'Berlian', 'Bernadeth', 'Berta', 'Betaria', 'Betty', 'Bia', 'Binar', 'Bintang'
]

FIRST_NAMES_FEMALE_JAPANESE = [
    'Hina', 'Yui', 'Mei', 'Mio', 'Aoi', 'Sakura', 'Koharu', 'Akari', 'Honoka', 'Yuna',
    'Rin', 'Ema', 'Nanami', 'Riko', 'Yuka', 'Misaki', 'Ayaka', 'Kana', 'Nanako', 'Tomomi',
    'Sayaka', 'Haruka', 'Rio', 'Sara', 'Kanna', 'Himari', 'Tsumugi', 'Ichika', 'Sana', 'Meisa',
    'Suzu', 'Kotone', 'Wakana', 'Miyu', 'Suzuka', 'Haruna', 'Nozomi', 'Ayano', 'Rina', 'Miku',
    'Airi', 'Shiori', 'Momoka', 'Saki', 'Mai', 'Asuka', 'Nana', 'Chihiro', 'Marina', 'Minori',
    'Hinata', 'Yuri', 'Kaori', 'Erika', 'Hitomi', 'Mariko', 'Kyoko', 'Risa', 'Rumi', 'Megumi',
    'Yukiko', 'Keiko', 'Yoko', 'Mayumi', 'Tomoko', 'Junko', 'Naoko', 'Miho', 'Chika', 'Ayumi',
    'Satomi', 'Nao', 'Saori', 'Miwa', 'Akane', 'Ai', 'Chiyo', 'Emiko', 'Fumiko', 'Hana',
    'Izumi', 'Kazuko', 'Maki', 'Noriko', 'Reiko', 'Sachiko', 'Tamiko', 'Ume', 'Yoshiko', 'Ami',
    'Chitose', 'Etsuko', 'Fusako', 'Harue', 'Itsuko', 'Kimiko', 'Masako', 'Nobuko', 'Rumiko', 'Shizuka',
    'Taeko', 'Wakako', 'Yukari', 'Asami', 'Fuyumi', 'Hisako', 'Kaede', 'Kikuko', 'Yua', 'Mayu',
    'Niko', 'Ruka', 'Kanon', 'Karen', 'Rena', 'Ayane', 'Mirei', 'Hanako', 'Kiyoko', 'Michiko',
    'Mitsuko', 'Shizuko', 'Tomiko', 'Toshiko', 'Chieko', 'Eiko', 'Hiroko', 'Setsuko', 'Teruko', 'Yasuko',
    'Kumiko', 'Aiko', 'Ayame', 'Chizuru', 'Emi', 'Erena', 'Hikari', 'Kaho', 'Kasumi', 'Kiko', 'Mami',
    'Mana', 'Manami', 'Mao', 'Midori', 'Mina', 'Mitsu', 'Miu', 'Miyabi', 'Moe', 'Nagisa',
    'Natsumi', 'Nene', 'Noa', 'Nonoka', 'Rei', 'Reina', 'Sato', 'Sayuri', 'Sora', 'Tomoka',
    'Wakaba', 'Kano'
]

FIRST_NAMES_FEMALE_KOREAN = [
    'Seo-yeon', 'Seo-yun', 'Ji-woo', 'Seo-hyeon', 'Min-seo', 'Ha-eun', 'Ha-yoon', 'Yoon-seo', 'Ji-ah', 'Chae-won',
    'Ji-an', 'Eun-seo', 'Da-eun', 'Ye-eun', 'Soo-ah', 'Yu-na', 'Ji-min', 'Hye-jin', 'Eun-ji', 'So-hee',
    'Bo-young', 'Na-yeon', 'Yu-jin', 'Su-bin', 'Ji-hyun', 'Min-ah', 'Chae-young', 'Da-hyun', 'Eun-bi', 'Ga-eun',
    'Ha-rin', 'Hye-ri', 'Ji-soo', 'Joo-hyun', 'Kyung-mi', 'Mi-so', 'Na-eun', 'Ryu-jin', 'Seul-gi', 'Tae-yeon',
    'Ye-ji', 'Yoon-ah', 'Bo-ra', 'Chae-yeon', 'Da-young', 'Eun-ha', 'Hani', 'Hwa-sa', 'Jennie', 'Joy',
    'Lisa', 'Mina', 'Momo', 'Na-kyung', 'Sana', 'Solar', 'Sun-mi', 'Tiffany', 'Wendy', 'Whee-in',
    'Ye-rim', 'Yu-qi', 'Bo-kyung', 'Cho-rong', 'Da-som', 'Eun-kyung', 'Hee-jin', 'Hye-won', 'Ji-eun', 'Joo-eun',
    'Mi-yeon', 'Na-young', 'Se-jeong', 'Su-ji', 'Ye-won', 'Ah-ra', 'Bo-mi', 'Chae-eun', 'Da-hee', 'Eun-young',
    'Ga-in', 'Ha-na', 'Hyo-rin', 'In-na', 'Jae-kyung', 'Ki-eun', 'Mi-rae', 'Na-ri', 'Ra-hee', 'Sa-rang',
    'So-min', 'Tae-hee', 'Won-young', 'Yeo-reum', 'Yu-ri', 'Bo-ah', 'Chun-hee', 'Dan-bi', 'Eun-hye', 'Goo-reum',
    'Ha-neul', 'Hyo-joo', 'Ji-won', 'Ju-hyun', 'Mi-ran', 'Na-ra', 'Ro-woon', 'Seon-ho', 'So-yoon', 'Yeo-jin',
    'Ae-jung', 'Ae-ran', 'Ae-ri', 'Ae-sook', 'Ba-da', 'Bo-ram', 'Cho-hee', 'Do-hee', 'Do-kyung', 'Do-yeon',
    'Eun-byul', 'Eun-chae', 'Eun-hee', 'Eun-jin', 'Eun-joo', 'Eun-jung', 'Eun-mi', 'Eun-min', 'Eun-sook', 'Eun-sun',
    'Ga-eul', 'Ga-ram', 'Ga-young', 'Geum-hee', 'Ha-ni', 'Ha-yan', 'Ha-young', 'Hae-in', 'Hae-jin', 'Hae-mi',
    'Hae-min', 'Hae-ryung', 'Hae-sook', 'Hae-won', 'Hana', 'Hee-jung', 'Hee-kyung', 'Hee-sun', 'Hee-young', 'Hyo-jin',
    'Hyo-jung', 'Hyo-yeon', 'Hyun-ah', 'Hyun-hee', 'Hyun-jin', 'Hyun-jung', 'Hyun-kyung', 'Hyun-mi', 'Hyun-sook', 'Hyun-young',
    'In-sook', 'In-young', 'Ji-hae', 'Ji-hye', 'Ji-yeon', 'Ji-a', 'Ji-yoon', 'Ye-rin', 'So-yul', 'Ji-yu',
    'Soo-bin', 'Min-ji', 'Si-eun', 'Ah-reum', 'Sae-ron', 'Cha-young', 'Da-hye', 'Hye-kyo', 'Jin-sol', 'Seo-jin',
    'Sin-b', 'So-won', 'Ye-bin', 'Yoo-jung', 'Yoon-ji', 'Jo-yi', 'Se-eun', 'Seung-yeon', 'So-mi', 'Sun-hwa',
    'Yoo-na', 'Young-ae', 'Cho-a', 'Moon-byul', 'Se-kyung', 'So-eun', 'So-yeon', 'Yoo-ri', 'Hye-sung', 'Joo-yeon',
    'Seol-hyun', 'So-jin', 'Soo-jin', 'Ye-seo', 'Yoon-chae', 'Yu-mi', 'A-ra', 'Bomi', 'Chaewon', 'Dami',
    'Eunsol', 'Gayeon', 'Kyung-ah', 'Nari', 'Raina', 'Sol-ji', 'Song-i', 'Subin', 'Yeon-hee', 'Ae-cha', 'Da-won',
    'Go-eun', 'Ha-yeon', 'Hye-jung', 'Hye-rim', 'Hye-su', 'In-hye', 'Ji-ae', 'Ji-young', 'Jin-a', 'Jin-hee',
    'Jin-ju', 'Ju-won', 'Jung-ah', 'Jung-eun', 'Jung-hwa', 'Jung-min', 'Mi-cha', 'Mi-hee', 'Mi-jung', 'Mi-kyung',
    'Mi-ok', 'Mi-sook', 'Mi-sun', 'Min-hee', 'Min-ju', 'Min-young', 'Seoah', 'Hayoon', 'Jian', 'Seoyoon',
    'Haeun', 'Ahrin', 'Jiwoo', 'Sua', 'Jia', 'Yuna', 'Dain', 'Siyeon', 'Eunseo', 'Soomin',
    'Yeseo', 'Nayun', 'Minseo', 'Jimin', 'Seoyeon', 'Taeyeon', 'Yoona', 'Sooyoung', 'Yuri', 'Hyoyeon',
    'Sunny', 'Seohyun', 'Irene'
]

FIRST_NAMES_FEMALE_RUSSIAN = [
    'Anna', 'Maria', 'Elena', 'Daria', 'Anastasia', 'Polina', 'Ekaterina', 'Ksenia', 'Victoria', 'Yulia',
    'Olga', 'Tatiana', 'Natalia', 'Irina', 'Svetlana', 'Alisa', 'Valeria', 'Veronika', 'Marina', 'Alina',
    'Yana', 'Diana', 'Kristina', 'Eva', 'Milana', 'Varvara', 'Ulyana', 'Margarita', 'Vasilisa', 'Arina',
    'Kira', 'Taisiya', 'Snezhana', 'Oksana', 'Nadezhda', 'Lyudmila', 'Galina', 'Larisa', 'Tamara', 'Zoya',
    'Evgeniya', 'Lidiya', 'Nina', 'Alla', 'Inna', 'Vera', 'Maya', 'Zlata', 'Eseniya', 'Agata',
    'Alena', 'Bela', 'Vlada', 'Dana', 'Evdokia', 'Zhanna', 'Zinaida', 'Ilona', 'Kseniya', 'Lada',
    'Mira', 'Nonna', 'Olesya', 'Pelageya', 'Rada', 'Serafima', 'Taisia', 'Ustina', 'Faina', 'Alevtina',
    'Bozhena', 'Vasilina', 'Glafira', 'Dina', 'Emiliya', 'Zemfira', 'Inga', 'Klara', 'Liliya', 'Sofiya',
    'Mariya', 'Viktoriya', 'Aleksandra', 'Anastasiya', 'Darya', 'Valeriya', 'Miroslava', 'Elizaveta', 'Angelina', 'Alexandra', 'Alyona',
    'Antonina', 'Evgenia', 'Lidia', 'Lilia', 'Liubov', 'Natasha', 'Nika', 'Viktoria', 'Yaroslava', 'Yekaterina',
    'Yesenia', 'Angelina', 'Lyubov', 'Ada', 'Adelaida', 'Adelina', 'Aglaya', 'Agripina', 'Ada', 'Aza',
    'Akulina', 'Albina', 'Amaliya', 'Anastasya', 'Anfisa', 'Anita', 'Anisiya', 'Anfisa', 'Apolinariya', 'Ariadna',
    'Asya', 'Aureliya', 'Aelita', 'Bella', 'Berta', 'Bogdana', 'Boleslava', 'Borislava', 'Bronislava', 'Valentina',
    'Vassa', 'Vesta', 'Violetta', 'Virineya', 'Vladilena', 'Vladislava', 'Vlasta', 'Ganna', 'Gayane', 'Glikeriya',
    'Gordana', 'Daniya', 'Dara', 'Darina', 'Dekabrina', 'Dinara', 'Dioniya', 'Diyana', 'Dominika', 'Domna',
    'Dora', 'Dorofeya', 'Evdokiya', 'Evlaliya', 'Evlampiya', 'Evpraksiya', 'Evrostiya', 'Elmira'
]

FIRST_NAMES_FEMALE_THAI = [
    'Kanya', 'Ratana', 'Apinya', 'Siriporn', 'Supaporn', 'Waraporn', 'Pornpimol', 'Nattaya', 'Sunisa', 'Malee',
    'Kulap', 'Anong', 'Patcharin', 'Sasithorn', 'Wannipa', 'Busaba', 'Chutima', 'Jintana', 'Pimchanok', 'Nicha',
    'Kanokwan', 'Benjamas', 'Chalida', 'Duangduan', 'Kamonchanok', 'Ladda', 'Maneerat', 'Narumon', 'Orawan', 'Piyathida',
    'Rungrat', 'Sopa', 'Thanyalak', 'Ubonrat', 'Vilai', 'Wilawan', 'Yupaporn', 'Anchalee', 'Boonsri', 'Chariya',
    'Darunee', 'Hathaikan', 'Jiraporn', 'Kritsana', 'Laddawan', 'Mayuree', 'Nongluck', 'Onanong', 'Pensri', 'Ratchanee',
    'Somjit', 'Tasanee', 'Uraiwan', 'Wandee', 'Yaowalak', 'Aranya', 'Buppha', 'Chawiwan', 'Daorung', 'Jarunee',
    'Kesara', 'Lamduan', 'Malai', 'Nuanchan', 'Pornthip', 'Ramida', 'Saengdao', 'Tipawan', 'Umaporn', 'Warunee',
    'Yupa', 'Bussakorn', 'Chanida', 'Dusadee', 'Kanchana', 'Lalita', 'Montha', 'Naphaporn', 'Pattama', 'Ruedee',
    'Suda', 'Thidarat', 'Viyada', 'Wipaporn', 'Amara', 'Boonreun', 'Chintana', 'Duangjai', 'Jintara', 'Kamonwan',
    'Kannika', 'Laksami', 'Malinee', 'Nantana', 'Oranuch', 'Pattarapon', 'Pranee', 'Rattikan', 'Sirilak', 'Somying',
    'Suphatra', 'Thassanee', 'Usa', 'Wimonrat', 'Yaowanit', 'Anchana', 'Bowranee', 'Chadaporn', 'Duangkamol', 'Hathairat',
    'Jaruwan', 'Kanyarat', 'Lamai', 'Mananya', 'Naree', 'Orrapan', 'Pavinee', 'Prapai', 'Rapeepan', 'Samorn',
    'Sirima', 'Suchada', 'Supranee', 'Theerarat', 'Umapat', 'Wilasinee', 'Yanin', 'Amonrat', 'Boonrawd', 'Chanpen',
    'Acharaporn', 'Amphon', 'Ananya', 'Apinporn', 'Arisara', 'Athitiya', 'Benyapa', 'Bowornlak', 'Buntharik', 'Chamaiporn',
    'Chanankida', 'Chanidapa', 'Chanya', 'Charatsri', 'Chatraporn', 'Chawisa', 'Chayanit', 'Chollada', 'Duangduean', 'Duangruthai',
    'Intira', 'Jarunrat', 'Jiranan', 'Jirapanya', 'Jittra', 'Kallaya', 'Kamonthip', 'Kanittha', 'Kannikar', 'Kanthima',
    'Kanyaphon', 'Kessuda', 'Khwanjai', 'Kirana', 'Kornkanya', 'Krittiya', 'Ladawan', 'Laksamon', 'Laksika', 'Manatsanan',
    'Marisa', 'Metinee', 'Monthira', 'Nanthana', 'Napasorn', 'Naphat', 'Naphatsawan', 'Nareerat', 'Natpaphat', 'Nattamon',
    'Natthakan', 'Natticha', 'Nichakorn', 'Niramol', 'Niratchaporn', 'Nisarat', 'Nittaya', 'Nongnuch', 'Nongyao', 'Nutchanart',
    'Oranit', 'Pakjira', 'Panadda', 'Panatda', 'Panisara', 'Pantila', 'Papatsara', 'Paramee', 'Parichat', 'Patitta',
    'Pattaranit', 'Payao', 'Peerada', 'Phanthira', 'Phatcharee', 'Phimpha', 'Pichamon', 'Piyanut', 'Pornthida', 'Pranom',
    'Suksom', 'Nonglak', 'Wanida', 'Kamonrat', 'Mayura', 'Orasa', 'Prapassorn', 'Rattana', 'Saowalak', 'Somhatai',
    'Sunee', 'Sureeporn', 'Thanaporn', 'Ampai', 'Daoroong', 'Kanjana', 'Nualchan', 'Pachara', 'Pimpa', 'Prasertporn',
    'Rojana', 'Sirinapa', 'Somruedee', 'Sunanta', 'Supatra', 'Surang', 'Thanyarat', 'Tipsuda', 'Vipaporn', 'Watcharaporn',
    'Yupin', 'Boonrueang', 'Dara', 'Jariya', 'Kwanjai', 'Nipaporn', 'Nuengruethai', 'Pailin', 'Ploy', 'Ruethai',
    'Somsri', 'Supannee', 'Suporn', 'Thasanee', 'Tuanjai', 'Usanee', 'Voranuch', 'Wilaiporn', 'Budsaba', 'Charuwan',
    'Duangporn', 'Jindarat', 'Kularb', 'Mali', 'Nuanphan', 'Piyaporn', 'Prapan', 'Ratsamee', 'Saengduan', 'Siriwan',
    'Sujitra', 'Suntaree', 'Supisara', 'Suwanna', 'Ubon', 'Vimon', 'Wanpen', 'Yada', 'Jitsuda', 'Monrudee',
    'Niramon', 'Orapan', 'Panida', 'Ployrat', 'Sanan', 'Siriphan', 'Somluck', 'Sukanya', 'Suthathip', 'Thipwimol',
    'Ubolrat', 'Wanna', 'Amporn', 'Bussaba', 'Chonticha', 'Dararat', 'Issaree', 'Janya', 'Methinee', 'Natthanicha',
    'Saranya', 'Waranya', 'Wassana', 'Amornrat', 'Amphai', 'Ampika', 'Angkana', 'Anongnat', 'Anoma', 'Anothai', 'Apatsara',
    'Areerat', 'Arunee', 'Benjawan', 'Boonreuan', 'Boontarika', 'Busarakam', 'Chadarat', 'Chaemchoi', 'Chaiyada', 'Chalita',
    'Chanakan', 'Chananporn', 'Chanapa', 'Chanikarn', 'Charanya', 'Charoenrat', 'Chatsuda', 'Chayanin', 'Chayapa', 'Chidchanok',
    'Chinda', 'Chiraporn', 'Chiranan', 'Chonlada', 'Chonthicha', 'Chotika', 'Chuanchom', 'Darika', 'Duangkamon', 'Duangmanee',
    'Duangnapa', 'Duangruedee', 'Duangta', 'Itsara', 'Janpen', 'Jantana', 'Jantira', 'Jarunya', 'Jirarat', 'Jirawan',
    'Juengjit', 'Kalaya', 'Kamonpan', 'Kamonporn', 'Kanda', 'Kanlayanee', 'Kanthida', 'Kanyaphak', 'Karnchana', 'Wannisa',
    'Patcharaporn', 'Kornkanok', 'Apsara', 'Chantana', 'Orathai', 'Phawinee', 'Wilai', 'Yaowapa', 'Chomsri', 'Dokmai',
    'Nuengruthai', 'Pitsamai', 'Ratree'
]

FIRST_NAMES_FEMALE_WESTERN = [
    'Olivia', 'Emma', 'Charlotte', 'Amelia', 'Sophia', 'Isabella', 'Ava', 'Mia', 'Evelyn', 'Luna',
    'Harper', 'Camila', 'Sofia', 'Scarlett', 'Elizabeth', 'Eleanor', 'Emily', 'Chloe', 'Mila', 'Violet',
    'Penelope', 'Gianna', 'Aria', 'Abigail', 'Ella', 'Avery', 'Hazel', 'Nora', 'Layla', 'Lily',
    'Aurora', 'Nova', 'Ellie', 'Madison', 'Grace', 'Isla', 'Willow', 'Zoe', 'Stella', 'Ivy',
    'Paisley', 'Addison', 'Natalie', 'Emilia', 'Maya', 'Genesis', 'Naomi', 'Elena', 'Sarah', 'Victoria',
    'Claire', 'Audrey', 'Savannah', 'Bella', 'Skylar', 'Lucy', 'Anna', 'Samantha', 'Caroline', 'Aaliyah',
    'Kennedy', 'Kinsley', 'Allison', 'Madelyn', 'Adeline', 'Alexa', 'Delilah', 'Serenity', 'Ashley', 'Andrea',
    'Alice', 'Peyton', 'Julia', 'Hailey', 'Autumn', 'Quinn', 'Eva', 'Piper', 'Sophie', 'Sadie',
    'Lydia', 'Clara', 'Vivian', 'Reagan', 'Melanie', 'Mackenzie', 'Brianna', 'Jade', 'Eliana', 'Emery',
    'Remi', 'Rose', 'Cora', 'Melody', 'Natalia', 'Athena', 'Maria', 'Leilani', 'Everly', 'Lillian',
    'Hannah', 'Brooklyn', 'Lilly', 'Charlie', 'Daisy', 'Reese', 'Emersyn', 'Sienna', 'Kylie', 'Norah',
    'Katelyn', 'Raelynn', 'Brielle', 'Jessica', 'Amanda', 'Jennifer', 'Melissa', 'Stephanie', 'Rebecca', 'Laura',
    'Sharon', 'Cynthia', 'Kathleen', 'Amy', 'Shirley', 'Angela', 'Helen', 'Brenda', 'Pamela', 'Nicole',
    'Katherine', 'Christine', 'Debra', 'Rachel', 'Carolyn', 'Janet', 'Catherine', 'Heather', 'Diane', 'Ruth',
    'Julie', 'Joyce', 'Virginia', 'Kelly', 'Christina', 'Joan', 'Judith', 'Megan', 'Cheryl', 'Martha',
    'Jacqueline', 'Frances', 'Ann', 'Teresa', 'Gloria', 'Sara', 'Janice', 'Jean', 'Doris', 'Judy',
    'Denise', 'Amber', 'Marilyn', 'Beverly', 'Danielle', 'Theresa', 'Diana', 'Brittany', 'Isabel', 'Kayla',
    'Alexis', 'Lori', 'Tiffany', 'Jane', 'Wendy', 'Cindy', 'Beth', 'Vicki', 'Priscilla', 'Monica',
    'Erica', 'Carla', 'Stacey', 'Gina', 'Robin', 'Amara', 'Amira', 'Anastasia', 'Annabelle', 'Ariana',
    'Arianna', 'Aubrey', 'Brooke', 'Carmen', 'Cecilia', 'Daniela', 'Eden', 'Eloise', 'Faith', 'Fiona',
    'Gabriella', 'Georgia', 'Hope', 'Iris', 'Riley', 'Seraphina', 'Abbie', 'Abby', 'Ada', 'Adelaide', 'Adele',
    'Adriana', 'Adrienne', 'Aileen', 'Aimee', 'Alana', 'Alani', 'Alanna', 'Alayna', 'Aleah', 'Alessandra',
    'Alex', 'Alexandra', 'Alexandria', 'Alexia', 'Alia', 'Alicia', 'Alina', 'Alisa', 'Alisha', 'Alison',
    'Alissa', 'Alivia', 'Aliyah', 'Allie', 'Ally', 'Allyson', 'Alma', 'Alondra', 'Alyson', 'Alyssa',
    'Amelie', 'America', 'Ana', 'Anahi', 'Anais', 'Anaya', 'Angel', 'Angelica', 'Angelina', 'Angeline',
    'Angelique', 'Angie', 'Anika', 'Anissa', 'Anita', 'Aniya', 'Aniyah', 'Annabel', 'Zoey', 'Leah',
    'Ruby', 'Valentina', 'Josephine', 'Nevaeh', 'Madeline', 'Rylee', 'Adaline', 'Adalyn', 'Addilyn', 'Adelyn',
    'Agatha', 'Ainsley', 'Alannah', 'Alejandra', 'Alena', 'Alessia', 'Aliya', 'Allisson', 'Amani', 'Amalia',
    'Amina', 'Amirah', 'Amya', 'Analia', 'Annabella', 'Annalise', 'Anne', 'Annie', 'Annika', 'Ansley',
    'Antoinette', 'Anya', 'April', 'Arabella', 'Aranza', 'Ariadna', 'Ariel', 'Ariella', 'Arielle', 'Ariyah',
    'Armani', 'Arya', 'Ashlee', 'Ashleigh', 'Ashlyn', 'Ashlynn', 'Aspen', 'Astrid', 'Aubree', 'Auden',
    'Augusta', 'Aurelia', 'Avah', 'Avalynn', 'Aviana', 'Avianna', 'Avril', 'Aya', 'Ayana', 'Ayla',
    'Ayleen', 'Aylin', 'Azalea', 'Azariah', 'Bailee', 'Bailey', 'Barbara', 'Beatrice', 'Beatrix', 'Belinda',
    'Belle', 'Bria', 'Briana', 'Brianne', 'Bridget', 'Briella', 'Brinley', 'Bristol', 'Brooklynn', 'Brylee',
    'Brynlee', 'Brynn', 'Cadence', 'Caitlin', 'Cali', 'Callie', 'Calliope', 'Cameron', 'Camilla', 'Camille',
    'Camryn', 'Cara', 'Carina', 'Carissa', 'Carly', 'Carolina', 'Carrie', 'Cassandra', 'Cassidy', 'Catalina',
    'Caylee', 'Cecelia', 'Cecily', 'Celeste', 'Celia', 'Celine', 'Chana', 'Chandler', 'Chanel', 'Charlee',
    'Charleigh', 'Charlene', 'Charley', 'Charli', 'Chaya', 'Chelsea', 'Cheyenne', 'Clare', 'Clarissa', 'Claudia',
    'Clementine', 'Cleo', 'Colette', 'Collins', 'Coral', 'Coralie', 'Cordelia', 'Corinne', 'Courtney', 'Crystal',
    'Dahlia', 'Dakota', 'Dallas', 'Dana', 'Danica', 'Daniella', 'Daphne', 'Dara', 'Darcy', 'Daria',
    'Davina', 'Dayana', 'Deborah', 'Deirdre', 'Delaney', 'Della', 'Demi', 'Desirae', 'Destiny', 'Dolly',
    'Dorothy', 'Dulce', 'Edith', 'Eileen', 'Elaine', 'Elianna', 'Elinor', 'Elisa', 'Elisabeth', 'Elise',
    'Eliza', 'Elle', 'Ellen', 'Elliana', 'Elliot', 'Elliott', 'Ellis', 'Elodie', 'Elsa', 'Elsie',
    'Elyse', 'Ember', 'Emelia', 'Emely', 'Emerald', 'Emerson', 'Emilie', 'Emmaline', 'Emmalyn', 'Emmalynn',
    'Emmanuelle', 'Emmeline', 'Emmie', 'Emmy', 'Erika', 'Erin', 'Esme', 'Esmeralda', 'Esperanza', 'Estelle',
    'Ester', 'Esther', 'Estrella', 'Ethel', 'Evangeline', 'Eve', 'Evelynn', 'Everlee', 'Everleigh', 'Evie',
    'Farah', 'Fatima', 'Fay', 'Faye', 'Felicity', 'Fernanda', 'Flora', 'Florence', 'Francesca', 'Frankie',
    'Freya', 'Freyja', 'Frida', 'Gabrielle', 'Gemma', 'Genevieve', 'Georgina', 'Gia', 'Giavanna', 'Gillian',
    'Ginger', 'Gisele', 'Giselle', 'Giada', 'Gladys', 'Gracelyn', 'Gracie', 'Greta', 'Gretchen', 'Guinevere',
    'Gwen', 'Gwendolyn', 'Hadley', 'Haleigh', 'Haley', 'Halle', 'Hallie', 'Hana', 'Hanna', 'Harlow',
    'Harlyn', 'Harmony', 'Harriet', 'Hattie', 'Haven', 'Hayden', 'Haylee', 'Hayley', 'Heidi', 'Helena',
    'Henley', 'Henrietta', 'Hilary', 'Holland', 'Holly', 'Hunter', 'Ida', 'Iliana', 'Imogen', 'India',
    'Ingrid', 'Irene', 'Isabela', 'Isabelle', 'Isobel', 'Itzel', 'Iva', 'Ivanna', 'Izabella', 'Jada',
    'Jaelyn', 'Jaime', 'Jana', 'Janelle', 'Janessa', 'Janie', 'Jasmine', 'Jaycee', 'Jayda', 'Jayde',
    'Jayden', 'Jayla', 'Jaylah', 'Jaylee', 'Jayleen', 'Jaylene', 'Jazmin', 'Jazmine', 'Jeanette', 'Jeanie',
    'Jenna', 'Jennie', 'Jenny', 'Jessie', 'Jewel', 'Jill', 'Jillian', 'Jimena', 'Joanna', 'Jocelyn',
    'Joelle', 'Jolene', 'Jolie', 'Jordyn', 'Joselyn', 'Josie', 'Joy', 'Jules', 'Juliana', 'Julianna',
    'Julianne', 'Juliet', 'Julieta', 'Juliette', 'June', 'Juniper', 'Justine', 'Kadence', 'Kaelyn', 'Kaia',
    'Kailani', 'Kailey', 'Kairi', 'Kaitlyn', 'Kaiya', 'Kali', 'Kaliyah', 'Kallie', 'Kamila', 'Kamryn',
    'Kara', 'Karen', 'Karina', 'Karla', 'Karsyn', 'Kassandra', 'Kassidy', 'Kate', 'Katelynn', 'Kathryn',
    'Katie', 'Katrina', 'Kay', 'Kaya', 'Kayden', 'Kaydence', 'Kaylee', 'Kayleigh', 'Kaylen', 'Kaylin',
    'Keira', 'Keitha', 'Kelley', 'Kelsey', 'Kendall', 'Kendra', 'Kenia', 'Kenley', 'Kenya', 'Kenzie',
    'Kiana', 'Kiara', 'Kiera', 'Kiersten', 'Kimber', 'Kimberly', 'Kimora', 'Kinley', 'Kinzley', 'Kira',
    'Kirsten', 'Kirstin', 'Kora', 'Kourtney', 'Kristen', 'Kristin', 'Kristina', 'Krystal', 'Kylee', 'Kyleigh',
    'Kynlee', 'Kyra', 'Lacey', 'Laila', 'Lailah', 'Lainey', 'Lana', 'Landrie', 'Landry', 'Laney',
    'Lara', 'Larissa', 'Laurel', 'Lauren', 'Lauryn', 'Lea', 'Leanna', 'Lena', 'Lennon', 'Lennox',
    'Leona', 'Lesley', 'Leslie', 'Leyla', 'Lia', 'Liana', 'Liberty', 'Lidia', 'Lilian', 'Liliana',
    'Lilianna', 'Lilith', 'Lilliana', 'Lillie', 'Lilyana', 'Lina', 'Linda', 'Lindsay', 'Lindsey', 'Lisa',
    'Liv', 'Livia', 'Lola', 'London', 'Londyn', 'Lorelei', 'Lorena', 'Lorna', 'Lorraine', 'Louisa',
    'Louise', 'Lucia', 'Luciana', 'Lucille', 'Lucinda', 'Luisa', 'Lyla', 'Lylah', 'Lynette', 'Mabel',
    'Maci', 'Macie', 'Macy', 'Madalyn', 'Madalynn', 'Maddison', 'Madeleine', 'Madelynn', 'Madilyn', 'Madilynn',
    'Madisyn', 'Mae', 'Maeve', 'Maggie', 'Magnolia', 'Maia', 'Maisie', 'Makayla', 'Makenna', 'Makenzie',
    'Malia', 'Maliyah', 'Mallory', 'Mara', 'Marceline', 'Margaret', 'Margarita', 'Margot', 'Mariah', 'Mariana',
    'Marianna', 'Marie', 'Marina', 'Marion', 'Marisa', 'Marisol', 'Marissa', 'Maritza', 'Marjorie', 'Marlee',
    'Marlene', 'Marley', 'Mary', 'Maryam', 'Matilda', 'Mattie', 'Mayra', 'Mckayla', 'Mckenna', 'Mckenzie',
    'Meadow', 'Meghan', 'Melany', 'Melina', 'Melinda', 'Mercer', 'Mercy', 'Meredith', 'Micah', 'Michaela',
    'Michelle', 'Mikaela', 'Mikayla', 'Milan', 'Milana', 'Milani', 'Milena', 'Miley', 'Millie', 'Mina',
    'Mira', 'Miracle', 'Miranda', 'Miriam', 'Molly', 'Monique', 'Morgan', 'Moriah', 'Mya', 'Myah',
    'Mylah', 'Myra', 'Nadia', 'Nadine', 'Nancy', 'Nataly', 'Natasha', 'Nathalie', 'Navy', 'Naya',
    'Nayeli', 'Nellie', 'Nia', 'Nicolette', 'Nieve', 'Nika', 'Nina', 'Noa', 'Noel', 'Noelle',
    'Noemi', 'Nola', 'Noor', 'Novalee', 'Nye', 'Nyla', 'Nylah', 'Oaklee', 'Oakleigh', 'Oakley',
    'Octavia', 'Odette', 'Olive', 'Opal', 'Ophelia', 'Paige', 'Paloma', 'Paola', 'Paris', 'Patricia',
    'Paula', 'Paulina', 'Pearl', 'Penny', 'Phoebe', 'Phoenix', 'Pippa', 'Polly', 'Poppy', 'Presley',
    'Rae', 'Raegan', 'Raelyn', 'Raina', 'Ramona', 'Raquel', 'Raven', 'Rayna', 'Rayne', 'Rebekah',
    'Regina', 'Remington', 'Rena', 'Renata', 'Renee', 'Reyna', 'Rhea', 'Rhiannon', 'Rhonda', 'Rian',
    'Rita', 'River', 'Rivka', 'Roberta', 'Robyn', 'Rochelle', 'Rory', 'Rosa', 'Rosalie', 'Rosalind',
    'Rosalyn', 'Roselyn', 'Rosemary', 'Rosie', 'Rowan', 'Roxanne', 'Ryann', 'Rylan', 'Ryleigh', 'Rylie',
    'Sabrina', 'Sage', 'Saige', 'Sally', 'Salma', 'Samara', 'Samira', 'Sandra', 'Sandy', 'Saoirse',
    'Sarai', 'Sasha', 'Sawyer', 'Saylor', 'Scarlette', 'Scout', 'Selena', 'Selene', 'Serena', 'Shae',
    'Shania', 'Shannon', 'Shay', 'Sheila', 'Shelby', 'Sierra', 'Silvia', 'Simone', 'Skye', 'Skyler',
    'Sloane', 'Sonia', 'Sonja', 'Sonya', 'Stacy', 'Susan', 'Susanna', 'Sutton', 'Sydney', 'Sylvia',
    'Tabitha', 'Talia', 'Tamara', 'Tamera', 'Tania', 'Tanya', 'Tara', 'Taryn', 'Tatiana', 'Tatum',
    'Teagan', 'Tessa', 'Thalia', 'Thea', 'Tia', 'Tiana', 'Tina', 'Tori', 'Tracy', 'Trinity',
    'Tyra', 'Valerie', 'Veda', 'Vera', 'Veronica', 'Vida', 'Violeta', 'Viviana', 'Vivienne', 'Waverly',
    'Whitney', 'Willa', 'Winnie', 'Winter', 'Wren', 'Wynne', 'Ximena', 'Xiomara', 'Yareli', 'Yaretzi',
    'Yasmin', 'Yasmine', 'Yvonne', 'Zara', 'Zaria', 'Zariyah', 'Zelda', 'Zendaya', 'Zhavia', 'Zoie',
    'Zola', 'Zora', 'Orla', 'Bonnie', 'Lottie', 'Darcie', 'Edie', 'Bethany', 'Carys', 'Catrin',
    'Ceridwen', 'Cerys', 'Eira', 'Elen', 'Ffion', 'Lowri', 'Mair', 'Nerys', 'Seren', 'Sian',
    'Ailidh', 'Beileag', 'Catriona', 'Eilidh', 'Iona', 'Kirsty', 'Mhairi', 'Morag', 'Rhona',
]

FIRST_NAMES_MALE_ARABIC = [
    'Mohammed', 'Ahmed', 'Ali', 'Omar', 'Hassan', 'Hussein', 'Khalid', 'Abdullah', 'Ibrahim', 'Mustafa',
    'Tariq', 'Zaid', 'Hamza', 'Youssef', 'Kareem', 'Bilal', 'Faisal', 'Saud', 'Mansour', 'Nasser',
    'Waleed', 'Rami', 'Sami', 'Rayan', 'Adel', 'Badr', 'Fahad', 'Ghassan', 'Hadi', 'Ihab',
    'Jalal', 'Kamal', 'Luay', 'Majid', 'Nabil', 'Osama', 'Qasim', 'Rashid', 'Salem', 'Talal',
    'Usama', 'Wael', 'Yahya', 'Ziyad', 'Amir', 'Bassem', 'Dawud', 'Fouad', 'Hani', 'Jamal',
    'Anas', 'Bashir', 'Diya', 'Farhan', 'Ghaith', 'Habib', 'Idris', 'Jad', 'Karam', 'Louai',
    'Munir', 'Nizar', 'Othman', 'Qais', 'Riyad', 'Sultan', 'Taha', 'Umar', 'Wajih', 'Yasin',
    'Ayman', 'Burhan', 'Duraid', 'Firas', 'Gazi', 'Harith', 'Ilyas', 'Jamil', 'Kassem', 'Lutfi',
    'Mahmoud', 'Khaled', 'Zayd', 'Amr', 'Karim', 'Saad', 'Mansoor', 'Faris', 'Yazan', 'Abbas', 'Abdul',
    'Adam', 'Ammar', 'Asad', 'Ashraf', 'Bassam', 'Fadi', 'Hisham', 'Imad', 'Ismail', 'Jaber',
    'Khalil', 'Mahdi', 'Malik', 'Marwan', 'Mazen', 'Mounir', 'Murad', 'Nader', 'Naji', 'Sabir',
    'Salah', 'Yusuf', 'Ghanem', 'Luqman', 'Zakariya', 'Abbas', 'Jafar', 'Abdulrahman', 'Abdulaziz', 'Abdulmajeed',
    'Abdulkarim', 'Abdulhadi', 'Abdulilah', 'Abdulwahed', 'Abdulghani', 'Abdulsalam', 'Abdullatif', 'Abdulbaqi', 'Abdulhakim', 'Abdulbari',
    'Abdulqadir', 'Abdulbasit', 'Abdulrazzaq', 'Abdulwahab', 'Abdulmalik', 'Abdulmohsen', 'Abdulmuhsin', 'Abdulkhaliq', 'Abdulwadood', 'Abdulhakeem',
    'Abdulmatin', 'Abdulwali', 'Abdulhamid', 'Abdulsamad', 'Abdulqayyum', 'Bahaa', 'Baqir', 'Baraka', 'Barkat', 'Bashar',
    'Bayan', 'Butros', 'Dhiya', 'Ehab', 'Emad', 'Fahd', 'Faiz', 'Fakhri', 'Faraj', 'Farid',
    'Faruq', 'Fath', 'Fathi', 'Fawwaz', 'Fawzi', 'Fayez', 'Fuad', 'Ghazi', 'Hafiz', 'Haitham',
    'Hakam', 'Hakim', 'Halim', 'Hamad', 'Hamdan', 'Hamid', 'Hammad', 'Harun', 'Hasan', 'Hashim',
    'Hatim'
]

FIRST_NAMES_MALE_BRAZILIAN = [
    'Gabriel', 'Lucas', 'Matheus', 'Pedro', 'Leonardo', 'Felipe', 'Bruno', 'Rodrigo', 'Thiago', 'Rafael',
    'Gustavo', 'Vinicius', 'Daniel', 'Marcelo', 'Eduardo', 'Andre', 'Caio', 'Diego', 'Vitor', 'Renan',
    'Igor', 'Arthur', 'Bernardo', 'Heitor', 'Davi', 'Lorenzo', 'Enzo', 'Theo', 'Samuel', 'Henrique',
    'Joao', 'Guilherme', 'Murilo', 'Nicolas', 'Lucca', 'Caua', 'Joaquim', 'Emanuel', 'Bento', 'Antonio',
    'Carlos', 'Francisco', 'Paulo', 'Marcos', 'Fernando', 'Roberto', 'Alexandre', 'Ricardo', 'Fabio', 'Leandro',
    'Adriano', 'Cristiano', 'Danilo', 'Evandro', 'Fabricio', 'Gilberto', 'Helio', 'Ivan', 'Julio', 'Kleber',
    'Almir', 'Benicio', 'Caetano', 'Elias', 'Fabiano', 'Geraldo', 'Hugo', 'Ismael', 'Joelson', 'Luan',
    'Marcio', 'Nelson', 'Otavio', 'Pietro', 'Ramiro', 'Sergio', 'Tiago', 'Valdir', 'Wagner', 'Alan',
    'Breno', 'Claudio', 'Dario', 'Edson', 'Flavio', 'Gilson', 'Italo', 'Jair', 'Laercio', 'Mauro',
    'Newton', 'Osvaldo', 'Pablo', 'Reginaldo', 'Silvio', 'Tulio', 'Vicente', 'William', 'Alex', 'Miguel',
    'Gael', 'Noah', 'Benjamin', 'Bryan', 'Isaac', 'Caleb', 'Erick', 'Giovanni', 'Kaique', 'Abel',
    'Abilio', 'Acacio', 'Adalberto', 'Adauto', 'Ademir', 'Aderbal', 'Adolfo', 'Afonso', 'Afranio', 'Agenor',
    'Aguinaldo', 'Airton', 'Alair', 'Alano', 'Albano', 'Albertino', 'Alberto', 'Albino', 'Alceu', 'Alcides',
    'Alcindo', 'Aldemir', 'Aldo', 'Alencar', 'Alessandro', 'Alfeu', 'Alfredo', 'Alipio', 'Alisson', 'Aloisio',
    'Alvaro', 'Amadeu', 'Amaro', 'Amauri', 'Americo', 'Amilcar', 'Amilton', 'Anacleto', 'Ananias', 'Anderson',
    'Anesio', 'Angelim', 'Angelo', 'Aniceto', 'Anisio', 'Antenor', 'Antero', 'Anthony', 'Antônio', 'Aparicio',
    'Apolonio', 'Aquiles', 'Araci', 'Ari', 'Ariel', 'Arildo', 'Aristeu', 'Aristides', 'Aristoteles', 'Arlindo',
    'Armando', 'Armindo', 'Arnaldo', 'Aroldo', 'Arquimedes', 'Artur', 'Ary', 'Assis', 'Atahualpa', 'Ataide',
    'Atila', 'Augusto', 'Aureliano', 'Aurelino', 'Aurelio', 'Aurino', 'Avelino', 'Balthazar', 'Baltazar', 'Barnabe',
    'Bartolomeu', 'Basilio', 'Batista', 'Belchior', 'Belisario', 'Belmiro', 'Benedito', 'Benito', 'Beraldo', 'Bernardino'
]

FIRST_NAMES_MALE_CHINESE = [
    'Wei', 'Hao', 'Jun', 'Jie', 'Chen', 'Yu', 'Yang', 'Bo', 'Tao', 'Lei',
    'Qiang', 'Peng', 'Chao', 'Feng', 'Long', 'Ming', 'Xin', 'Liang', 'Hui', 'Gang',
    'Dong', 'Yong', 'Bin', 'Rui', 'Kai', 'Cheng', 'Yi', 'Lin', 'Nan', 'Kun',
    'Zhe', 'Tian', 'Zheng', 'Jian', 'Ping', 'Xiang', 'Bao', 'Fan', 'Guo', 'Hang',
    'Jin', 'Lun', 'Quan', 'Sen', 'Shuo', 'Ting', 'Wen', 'Xiao', 'Yan', 'Yue',
    'Zhan', 'Zhi', 'Zihao', 'Yuxuan', 'Haoyu', 'Yichen', 'Yinuo', 'Zihan', 'Haoran', 'Xing',
    'Zimo', 'Boqian', 'Tianrui', 'Jiarui', 'Mingzhe', 'Yufan', 'Haochen', 'Chenxi', 'Zixuan', 'Zichen',
    'Ruochen', 'Muyang', 'Hongyu', 'Junjie', 'Tianyu', 'Xinyu', 'Boyuan', 'Yize', 'Zikang', 'Jingyu',
    'Shihan', 'Ruilin', 'Mingxuan', 'Yuchen', 'Bowen', 'Zirui', 'Zehao', 'Zhiyuan', 'Yulong', 'Zicheng',
    'Wenbo', 'Chengyu', 'Yuyang', 'Haotian', 'Zeyu', 'Yifan', 'Hengyu', 'Mingze', 'Zixu', 'Chengrui',
    'Jiahao', 'Boyang', 'Runze', 'Yijie', 'Guangyu', 'Shenghao', 'Xize', 'Jiacheng', 'Bolin', 'Chaoqun',
    'Dingkang', 'Enlai', 'Fangzhou', 'Guoliang', 'Hongrui', 'Jiayuan', 'Kaitian', 'Lianjie', 'Menglong', 'Nianzu',
    'Peiran', 'Qingshan', 'Rongsen', 'Shunfeng', 'Tongzhou', 'Wenchao', 'Xiangdong', 'Yuefeng', 'Zhaoxiang', 'Zhenhua',
    'Anbang', 'Baolong', 'Chuanqi', 'Dezheng', 'Enyang', 'Feifan', 'Guangming', 'Hongtao', 'Jianfeng', 'Kangtai',
    'Lingyu', 'Maolin', 'Ningyuan', 'Peilin', 'Qingyang', 'Rongguang', 'Shaopeng', 'Tianhao', 'Wenze', 'Xingchen',
    'Yuxin', 'Zhaoyu', 'Zhengyang', 'Boming', 'Chenglin', 'Dawei', 'Fangzheng', 'Guozhi', 'Haoming', 'Jianing',
    'An', 'Bai', 'Ben', 'Biao', 'Bing', 'Boshen', 'Chang', 'Changqing', 'Chaoxiang', 'Chenglong',
    'Chengwei', 'Chong', 'Chuan', 'Cong', 'Da', 'Dachuan', 'Dalong', 'Dan', 'De', 'Deming',
    'Ding', 'Donghai', 'Fa', 'Fang', 'Fu', 'Fucheng', 'Gen', 'Geng', 'Gong', 'Guang',
    'Guanghui', 'Gui', 'Guodong', 'Hai', 'Haifeng', 'Hailong', 'Haodong', 'He', 'Heng', 'Hong',
    'Hongbo', 'Honggang', 'Hongjun', 'Hongliang', 'Hongwei', 'Hou', 'Hu', 'Hua', 'Huan', 'Huang',
    'Huiliang', 'Jia', 'Jiachun', 'Jiade', 'Jiafu', 'Jiahong', 'Jiajun', 'Jialiang', 'Jiaming', 'Jianan',
    'Jianbo', 'Jiang', 'Jiangao', 'Jianguo', 'Jianhua', 'Jianjun', 'Jianliang', 'Jianming', 'Jianping', 'Jianqiang',
    'Jianrong', 'Jiansheng', 'Jianwei', 'Jianwen', 'Jianxiang', 'Sheng', 'Shuai', 'Zhong', 'Jiahui', 'Sicheng',
    'Xiangyu', 'Yuheng', 'Zijian', 'Fei', 'Ji', 'Jing', 'Kang', 'Ke', 'Lu', 'Miao',
    'Ning', 'Pan', 'Pei', 'Pu', 'Qi', 'Qian', 'Qing', 'Ren', 'Rong', 'Shan',
    'Song', 'Tai', 'Teng', 'Tong', 'Wan', 'Wu', 'Xi', 'Xian', 'Xiong', 'Xu',
    'Xue', 'Xun', 'Ya', 'Ye', 'Yin', 'You', 'Yuan', 'Yun', 'Zan', 'Ze',
    'Zhao', 'Zhen', 'Zhou', 'Zhu', 'Zhuo', 'Zong', 'Ao', 'Ba', 'Bi', 'Can',
    'Ce', 'Chun', 'Ci', 'Cui', 'Dian', 'Diao', 'Du', 'Duan', 'En', 'Gao',
    'Ge', 'Guan', 'Han', 'Haoqi', 'Huai', 'Jiawei', 'Jingbo', 'Jinghua', 'Junfeng', 'Junhao',
    'Junqiang', 'Junwei', 'Kaiwen', 'Kailun', 'Lingyun', 'Minghao', 'Mingjie', 'Peihua', 'Qinghai', 'Rongbo',
    'Shaohua', 'Shiwei', 'Shujun', 'Tiancheng', 'Wenhua', 'Wenjie', 'Wenlong', 'Wenzhe', 'Xiaobo', 'Xiaofeng',
    'Xiaogang', 'Xiaojun', 'Xiaoliang', 'Xiaoming', 'Xiaopeng', 'Xiaowei', 'Xiaoyong', 'Xinghua', 'Xingyu', 'Yonggang',
    'Yonghua', 'Yongjun', 'Yongqiang', 'Yongwei', 'Yuanbo', 'Yuanning', 'Zhenwei', 'Zhihua', 'Zhijun', 'Zhiming',
    'Zhiqiang', 'Fulin', 'Guofeng', 'Jiabin', 'Jianhao', 'Jingfei', 'Jingwei', 'Junhong', 'Kaicheng', 'Kaixuan', 'Leiming',
    'Li', 'Ling', 'Meng', 'Min', 'Mingda', 'Mingyu', 'Chenhao', 'Junxian', 'Yuze', 'Ziteng',
    'Boran', 'Ruolin', 'Zhengxuan', 'Zepeng', 'Rongxuan', 'Xuanrui', 'Yuming', 'Yuntian', 'Haoxuan', 'Yunkai',
    'Zhengyi', 'Tianshuo', 'Yutong'
]

FIRST_NAMES_MALE_FILIPINO = [
    'Joshua', 'Angelo', 'Christian', 'Mark', 'John', 'Michael', 'Gabriel', 'Daniel', 'Paolo', 'Kenneth',
    'Justin', 'Kevin', 'Bryan', 'Carlo', 'Rafael', 'Jeric', 'Francis', 'Alden', 'Dingdong', 'Bong',
    'Jun', 'Manny', 'Noel', 'Rene', 'Arnel', 'Benjie', 'Crisanto', 'Danilo', 'Edgardo', 'Ferdinand',
    'Gerardo', 'Hernan', 'Isagani', 'Joel', 'Kiko', 'Lito', 'Marvin', 'Nestor', 'Orlando', 'Pepito',
    'Quirino', 'Ramil', 'Salvador', 'Tirso', 'Ulysses', 'Vicente', 'Wilfredo', 'Xerxes', 'Yul', 'Zaldy',
    'Ace', 'Bam', 'Cesar', 'Dante', 'Efren', 'Froilan', 'Gil', 'Hermie', 'Inigo', 'Jobert',
    'Nathaniel', 'James', 'Carl', 'Miguel', 'Alexander', 'David', 'Anthony', 'Paul', 'Jerome', 'Adrian',
    'Lester', 'Ronnie', 'Eduardo', 'Fernando', 'Ramon', 'Reynaldo', 'Rogelio', 'John Paul', 'Jayson', 'Dominic',
    'Vincent', 'Patrick', 'Alvin', 'Darwin', 'Erick', 'Gerald', 'Harold', 'Ian', 'Karl', 'Lawrence',
    'Marlon', 'Neil', 'Oliver', 'Peter', 'Rodel', 'Sherwin', 'Tristan', 'Victor', 'Warren', 'Xavier',
    'Zoren', 'Benhur', 'Florante', 'Gorgonio', 'Hermogenes', 'Jovito', 'Kristoffer', 'Lamberto', 'Macario', 'Primitivo',
    'Teodoro', 'Abe', 'Abel', 'Abelardo', 'Abraham', 'Adolfo', 'Agapito', 'Agustin', 'Alberto', 'Alejandro',
    'Alex', 'Alfio', 'Alfonso', 'Alfred', 'Alfredo', 'Allen', 'Almar', 'Alonzo', 'Amado', 'Amador',
    'Ambrosio', 'Amiel', 'Anacleto', 'Anastacio', 'Andres', 'Aniceto', 'Antonio', 'Apolinario', 'Aquilino', 'Aris',
    'Arman', 'Armando', 'Arnulfo', 'Arsenio', 'Arthur', 'Arturo', 'Arvin', 'Asisclo', 'Aurelio', 'Basilio',
    'Bayani', 'Benedicto', 'Benjamin', 'Benito', 'Bernabe', 'Bernardo', 'Bienvenido', 'Blas', 'Bonifacio', 'Braulio',
    'Buenaventura', 'Caesar', 'Calixto', 'Camilo', 'Candido', 'Carlos', 'Casimiro', 'Catalino', 'Cecilio', 'Cedric',
    'Celedonio', 'Celestino', 'Charles', 'Cirilo', 'Ciriaco', 'Claro', 'Clemente', 'Conrado', 'Cornelio', 'Crispin',
    'Cristobal', 'Damaso', 'Dario', 'Demetrio', 'Dexter', 'Diego', 'Dionisio', 'Diosdado', 'Domingo', 'Donato',
    'Edgar', 'Edilberto', 'Edmundo', 'Eleuterio', 'Eliseo', 'Emeterio', 'Emil', 'Emiliano', 'Emilio', 'Emmanuel',
    'Enrico', 'Enrique', 'Epifanio', 'Erasmo'
]

FIRST_NAMES_MALE_INDIAN = [
    'Aarav', 'Vivaan', 'Aditya', 'Vihaan', 'Arjun', 'Sai', 'Reyansh', 'Ayan', 'Krishna', 'Ishan',
    'Shaurya', 'Atharv', 'Advik', 'Pranav', 'Kabir', 'Aryan', 'Dhruv', 'Ritvik', 'Ansh', 'Kian',
    'Rohan', 'Ayush', 'Dev', 'Parth', 'Harshit', 'Kunal', 'Manish', 'Rahul', 'Sachin', 'Amit',
    'Abhishek', 'Deepak', 'Gaurav', 'Mohit', 'Rajesh', 'Sandeep', 'Sanjay', 'Suresh', 'Varun', 'Vikas',
    'Vikram', 'Vivek', 'Yash', 'Alok', 'Nikhil', 'Pankaj', 'Rohit', 'Sumit', 'Tarun', 'Vishal',
    'Akshay', 'Ajay', 'Anil', 'Arvind', 'Ashish', 'Bharat', 'Chandan', 'Chetan', 'Dinesh', 'Hemant',
    'Jitendra', 'Kapil', 'Mahesh', 'Naveen', 'Neeraj', 'Nitin', 'Prakash', 'Rakesh', 'Ravi', 'Saurabh',
    'Sunil', 'Vinod', 'Samar', 'Veer', 'Shivam', 'Nakul', 'Madhav', 'Mayank', 'Harsh', 'Tanmay',
    'Tushar', 'Abhinav', 'Chirag', 'Tejas', 'Rishabh', 'Hardik', 'Shubham', 'Kartik', 'Aniket', 'Bhavesh',
    'Devendra', 'Gajendra', 'Himanshu', 'Jayant', 'Kuldeep', 'Lokesh', 'Mukesh', 'Narendra', 'Omprakash', 'Pawan',
    'Radhe', 'Satish', 'Trilok', 'Umesh', 'Vimal', 'Yogesh', 'Akash', 'Anmol', 'Brijesh', 'Chinmay',
    'Darshan', 'Eshan', 'Girish', 'Hitesh', 'Inder', 'Jagdish', 'Keshav', 'Lakshya', 'Manan', 'Naman',
    'Om', 'Piyush', 'Raghav', 'Samarth', 'Tanishq', 'Utkarsh', 'Vedant', 'Yashwant', 'Zaid', 'Arman',
    'Farhan', 'Imran', 'Sameer', 'Salman', 'Tariq', 'Zain', 'Aman', 'Anand', 'Anurag', 'Avinash',
    'Bhavin', 'Bhupendra', 'Chaitanya', 'Damodar', 'Deepesh', 'Devang', 'Dhanush', 'Dilip', 'Gautam', 'Gopal',
    'Govind', 'Gurcharan', 'Hari', 'Harish', 'Indrajit', 'Ishwar', 'Jagannath', 'Jatin', 'Kamal', 'Karan',
    'Kaushik', 'Kishore', 'Laxman', 'Madhu', 'Mandar', 'Manoj', 'Milind', 'Murali', 'Nandkishore', 'Narayan',
    'Naresh', 'Nilkanth', 'Pramod', 'Prashant', 'Purushottam', 'Raghu', 'Rajeev', 'Rajendra', 'Raman', 'Ramesh',
    'Ratan', 'Rishi', 'Sadashiv', 'Satyendra', 'Shailesh', 'Shantanu', 'Sharad', 'Shekhar', 'Shiva', 'Shyam',
    'Siddharth', 'Sohan', 'Subhash', 'Sudhanshu', 'Sudhir', 'Suraj', 'Tejinder', 'Upendra', 'Vasant', 'Venkatesh',
    'Ishaan', 'Rudra', 'Devansh', 'Kiaan', 'Ayaan', 'Shivansh', 'Darsh', 'Krrish', 'Daksh', 'Aniruddh',
    'Avyan', 'Yug', 'Shlok', 'Ranveer', 'Rachit', 'Divyansh', 'Eklavya', 'Lalit', 'Pushkar', 'Vidyut',
    'Waman', 'Yuvan', 'Zeeshan', 'Kailash', 'Chandresh', 'Dharmendra', 'Abhay', 'Amey', 'Anupam', 'Ashok',
    'Atul', 'Bhuvan', 'Aayush', 'Arnav', 'Shreyas', 'Tanish', 'Armaan', 'Abhimanyu', 'Hridaan', 'Ronit',
    'Yuvaan', 'Vansh', 'Jayden', 'Charvik', 'Dhaval', 'Gaurang', 'Kanav', 'Kartikeya', 'Luv', 'Manav',
    'Mihir', 'Mitansh', 'Moksh', 'Naitik', 'Nihar', 'Nishant', 'Ojas', 'Palash', 'Praneel', 'Pulkit',
    'Rajveer', 'Rithvik', 'Romir', 'Sachit', 'Saksham', 'Samaksh', 'Samrat', 'Sanchit', 'Sarthak', 'Shaan',
    'Shardul', 'Sparsh', 'Sujal', 'Sushant', 'Swarit', 'Tanush', 'Vaibhav', 'Vatsal', 'Vidit', 'Vihan',
    'Vinay', 'Viren', 'Vismay', 'Vivan', 'Vyom', 'Yashwardhan', 'Achyut', 'Adhiraj', 'Agastya', 'Ajit',
    'Akhil', 'Amar', 'Amartya', 'Apoorv', 'Ashutosh', 'Balraj', 'Deven', 'Divyesh', 'Gagan', 'Jaideep',
    'Kamlesh', 'Kripal', 'Madan', 'Mohan', 'Pradeep', 'Praveen', 'Prem', 'Ravindra', 'Sanjeev', 'Santosh',
    'Shashi', 'Shiv', 'Somesh', 'Subir', 'Uday', 'Vijay', 'Vipin', 'Virendra', 'Ankit', 'Arun',
    'Ayushman', 'Brij', 'Devraj', 'Jayesh', 'Nirmal', 'Prasad', 'Rajan', 'Ram', 'Rupesh', 'Siddhant',
    'Vasudev', 'Vinayak', 'Vishnu', 'Yatin', 'Aaditya', 'Aakash', 'Abhijeet', 'Abhilash', 'Adarsh', 'Adheesh', 'Akshaj',
    'Ameya', 'Anirban', 'Anjan', 'Ankur', 'Anshul', 'Apurv', 'Arav', 'Arihan', 'Arindam', 'Arjit',
    'Ashwath', 'Avik', 'Ayushmaan', 'Balamurali', 'Basant', 'Bhagvat', 'Bhanu', 'Bhaskar', 'Chanakya', 'Chintan',
    'Debashish', 'Dhananjay', 'Dharmesh', 'Digvijay', 'Dipen', 'Divakar', 'Divyanshu', 'Durgesh', 'Dwij', 'Eshwar',
    'Gandharv', 'Ganesh', 'Gokul', 'Gunjan', 'Harikrishnan', 'Hemang', 'Ishant', 'Jaydeep', 'Joydeep', 'Kalpesh',
    'Kamesh', 'Kandarp', 'Kashyap', 'Kaushal', 'Kavi', 'Kedar', 'Kiran', 'Lavanya', 'Madhavan', 'Mahendra',
    'Manas', 'Muhammad', 'Advaith', 'Aaryan', 'Ananya', 'Aarush', 'Nirvaan', 'Aaditya', 'Kush', 'Laksh',
    'Neil', 'Reyan', 'Ivaan', 'Pratyush', 'Abhiram'
]

FIRST_NAMES_MALE_INDONESIAN = [
    'Budi', 'Agus', 'Eko', 'Joko', 'Dian', 'Rizky', 'Fajar', 'Dimas', 'Hendra', 'Arif',
    'Aditya', 'Bayu', 'Gilang', 'Bagus', 'Ilham', 'Wahyu', 'Dwi', 'Indra', 'Tri', 'Agung',
    'Pratama', 'Surya', 'Rian', 'Doni', 'Rudi', 'Satria', 'Yoga', 'Farhan', 'Irfan', 'Rahmat',
    'Bambang', 'Candra', 'Dedi', 'Edi', 'Firmansyah', 'Gunawan', 'Hadi', 'Iskandar', 'Januar', 'Krisna',
    'Lukman', 'Mahendra', 'Nugraha', 'Oki', 'Pandu', 'Raden', 'Sandi', 'Taufik', 'Untung', 'Viktor',
    'Wawan', 'Yanto', 'Zainal', 'Ade', 'Bagas', 'Danang', 'Erick', 'Ferry', 'Gede', 'Haris',
    'Iwan', 'Jefri', 'Kurniawan', 'Lutfi', 'Mario', 'Nico', 'Panji', 'Rangga', 'Sigit', 'Teguh',
    'Usman', 'Vicky', 'Wisnu', 'Yogi', 'Zakaria', 'Aldi', 'Bima', 'Dharma', 'Erwin', 'Fikri',
    'Bintang', 'Rafi', 'Aris', 'Prasetyo', 'Abdi', 'Ahmad', 'Akbar', 'Ali', 'Andi', 'Andre', 'Anom',
    'Ardi', 'Arief', 'Arya', 'Bagap', 'Baskoro', 'Bimo', 'Bram', 'Cahyo', 'Chandra', 'Darma',
    'Denny', 'Dodi', 'Fauzi', 'Galang', 'Hafiz', 'Hamzah', 'Hari', 'Hartono', 'Hasan', 'Heru',
    'Hidayat', 'Imam', 'Iqbal', 'Jaka', 'Kurnia', 'Nugroho', 'Abdi', 'Abdillah', 'Abdurrahman', 'Achmad',
    'Adam', 'Adhi', 'Adhitya', 'Adi', 'Adnan', 'Agam', 'Aji', 'Alfian', 'Alif', 'Alvin',
    'Amir', 'Ananda', 'Andhika', 'Andra', 'Andreas', 'Angga', 'Anjar', 'Anton', 'Anwar', 'Apri',
    'Aprillio', 'Ardiansyah', 'Ardy', 'Ares', 'Ari', 'Arie', 'Arifin', 'Ario', 'Arman', 'Aryo',
    'Asrul', 'Asep', 'Ashari', 'Bachtiar', 'Badar', 'Bahrul', 'Bani', 'Basuki', 'Budhy', 'Budiman',
    'Cecep', 'Chairul', 'Christ', 'Christian', 'Dadan', 'Dadang', 'Daffa', 'Dani', 'Daniel', 'Danu',
    'Darmawan', 'Darsono', 'Daud'
]

FIRST_NAMES_MALE_JAPANESE = [
    'Ren', 'Haruto', 'Yuto', 'Sota', 'Riku', 'Minato', 'Haruki', 'Kento', 'Ryota', 'Kaito',
    'Daiki', 'Souta', 'Hayato', 'Yamato', 'Yuma', 'Kenji', 'Kazuki', 'Shota', 'Naoki', 'Shin',
    'Hiroshi', 'Takumi', 'Kenta', 'Daisuke', 'Tatsuya', 'Sho', 'Yuta', 'Kota', 'Sora', 'Ryusei',
    'Taiga', 'Asahi', 'Hinata', 'Itsuki', 'Yuuki', 'Kosuke', 'Ryosuke', 'Tomoya', 'Ryuki', 'Keita',
    'Makoto', 'Kazuma', 'Shinji', 'Takashi', 'Shingo', 'Kenichi', 'Masato', 'Jun', 'Hidetoshi', 'Yuya',
    'Shun', 'Taichi', 'Ryoma', 'Genki', 'Masahiro', 'Shintaro', 'Kohei', 'Yuki', 'Koki', 'Sosuke',
    'Ryuto', 'Kazuto', 'Kanata', 'Reo', 'Ayato', 'Ibuki', 'Haru', 'Ryo', 'Taro', 'Jiro',
    'Saburo', 'Shiro', 'Goro', 'Ichiro', 'Ken', 'Toru', 'Akira', 'Osamu', 'Satoshi', 'Isamu',
    'Tadashi', 'Akihiro', 'Bunji', 'Daichi', 'Eiji', 'Fumio', 'Gaku', 'Hideki', 'Issei', 'Junya',
    'Katsumi', 'Masaaki', 'Noboru', 'Ryuichi', 'Seiji', 'Tetsuo', 'Wataru', 'Yoshiaki', 'Atsushi', 'Chikao',
    'Eiichi', 'Fujio', 'Go', 'Hajime', 'Ikuo', 'Jo', 'Kazuhiro', 'Mamoru', 'Naoto', 'Reiji',
    'Susumu', 'Toshio', 'Yasushi', 'Zen', 'Bunta', 'Danno', 'Etsuo', 'Aoi', 'Hiroto', 'Yuuto',
    'Rento', 'Yuuma', 'Ryosei', 'Takuya', 'Shoma', 'Keisuke', 'Hiroki', 'Taiki', 'Kazuya', 'Tsubasa',
    'Rikuto', 'Tatsuo', 'Masashi', 'Tetsuya', 'Yuji', 'Hitoshi', 'Shigeru', 'Tsutomu', 'Mitsuru', 'Minoru',
    'Akihiko', 'Fumihiko', 'Hideaki', 'Junichi', 'Katsuhiko', 'Masahiko', 'Norihiko', 'Shinichi', 'Toshihiko', 'Yoshihiko', 'Arata',
    'Kaoru', 'Kazuo', 'Kouta', 'Masaki', 'Ryoto', 'Satoru', 'Takahiro', 'Taketo', 'Toa', 'Tsuyoshi',
    'Yasu', 'Yota', 'Yu', 'Yukio', 'Toma', 'Dan', 'Souma', 'Kouki', 'Kenshin'
]

FIRST_NAMES_MALE_KOREAN = [
    'Min-jun', 'Seo-jun', 'Do-yun', 'Ye-jun', 'Si-woo', 'Ha-joon', 'Ju-won', 'Ji-ho', 'Joon-woo', 'Hyun-woo',
    'Gun-woo', 'Woo-jin', 'Sun-woo', 'Seo-jin', 'Yeon-woo', 'Min-jae', 'Yu-jun', 'Dong-hyun', 'Seung-woo', 'Ji-hoon',
    'Sung-min', 'Jae-hyun', 'Jin-woo', 'Tae-hyun', 'Young-ho', 'Sang-won', 'Jung-hoon', 'Min-kyu', 'Tae-min', 'Seung-hyun',
    'Min-hyuk', 'Jin-young', 'Joon-ho', 'Sung-hoon', 'Dong-gun', 'Hyun-seok', 'Jae-won', 'Kwang-min', 'Myung-hoon', 'Sang-min',
    'Tae-woo', 'Won-bin', 'Young-jae', 'Bo-gum', 'Chan-yeol', 'Eun-woo', 'Geon-hoo', 'Hee-chul', 'Il-sung', 'Jong-in',
    'Kyung-soo', 'Min-seok', 'Nam-joon', 'Ro-woon', 'Seok-jin', 'Tae-hyung', 'Woo-shik', 'Yo-han', 'Jung-kook', 'Ji-min',
    'Ho-seok', 'Yoon-gi', 'Byung-hun', 'Dong-wook', 'Hye-sung', 'In-sung', 'Jin-mo', 'Ki-woong', 'Min-ho', 'Seung-gi',
    'So-ji', 'Tae-hee', 'Won-ho', 'Yong-hwa', 'Jae-suk', 'Dong-yeop', 'Ho-dong', 'Soo-hyun', 'Hyun-bin', 'Jung-min',
    'Kang-in', 'Kyung-ho', 'Myung-soo', 'Pil-sung', 'Sang-hyeok', 'Seung-ri', 'Tae-yang', 'Woo-bin', 'Yong-jun', 'Young-kwang',
    'Bae-jin', 'Chan-woo', 'Dae-sung', 'Eun-hyuk', 'Gwang-soo', 'Hee-jun', 'In-pyo', 'Jae-bum', 'Ki-bum', 'Man-seok',
    'Min-woo', 'No-min', 'Pyung-hwa', 'Sang-wook', 'Se-hoon', 'Si-hwan', 'Tae-hwan', 'Wook-jin', 'Ye-sung', 'Yoon-ho',
    'Bo-hyun', 'Chang-min', 'Do-hyun', 'Eun-seok', 'Ha-neul', 'Hyo-shin', 'Il-hoon', 'Jong-suk', 'Kwang-hee', 'Moon-bin',
    'Niel', 'Rae-won', 'San-deul', 'Seung-ho', 'Tae-il', 'Won-sik', 'Ye-won', 'Yong-guk', 'Young-woong', 'Zico',
    'Baek-hyeon', 'Bong-chul', 'Bong-gu', 'Bong-joon', 'Byung-cheol', 'Byung-doo', 'Byung-ho', 'Byung-joon', 'Byung-kwan', 'Byung-min',
    'Byung-sun', 'Byung-woo', 'Chan-hee', 'Chan-ho', 'Chan-hyuk', 'Chan-il', 'Chan-young', 'Chang-bum', 'Chang-ho', 'Chang-hoon',
    'Chang-hwan', 'Chang-seok', 'Chang-woo', 'Chang-yeol', 'Cheol-min', 'Cheol-soo', 'Cheol-woo', 'Chi-won', 'Chul-hee', 'Dae-chul',
    'Dae-han', 'Dae-hee', 'Dae-ho', 'Dae-hyun', 'Dae-jung', 'Dae-seok', 'Dae-won', 'Do-gyum', 'Do-hoon', 'Do-hyuk',
    'Do-il', 'Do-jin', 'Do-kwan', 'Do-won', 'Dong-chul', 'Dong-ha', 'Dong-ho', 'Dong-hoon', 'Dong-hyuk', 'Dong-il',
    'Dong-jin', 'Dong-jun', 'Dong-min', 'Dong-seok', 'Dong-soo', 'Dong-won', 'Dong-woo', 'Du-ho', 'Eun-chul', 'Eun-il',
    'Eun-jun', 'Eun-tae', 'Geon-woo', 'Gi-bum', 'Gi-cheol', 'Gi-dong', 'Gi-hong', 'Gi-hoon', 'Gi-hwan', 'Gi-moon',
    'Gi-seok', 'Gi-taek', 'Gi-woong', 'Gwang-chul', 'Gwang-hee', 'Gwang-hoon', 'Gwang-il', 'Gwang-jin', 'Gwang-min', 'Gwang-seok',
    'Gwang-tae', 'Hak-joon', 'Joo-won', 'Ji-hu', 'Hyun-jun', 'Jung-woo', 'Si-won', 'Jun-seo', 'Kang-min', 'Da-won',
    'Jun-ho', 'Ki-tae', 'Byeong-hun', 'Gyeong-su', 'Hyeon-seok', 'Jong-kook', 'Jun-su', 'Sang-woo', 'Do-hwan', 'Eui-gun',
    'Geun-suk', 'Han-bin', 'Hyo-seop', 'In-guk', 'San-ha', 'Se-hun', 'Si-hyuk', 'Sung-jae', 'Young-hoon', 'Jae-yoon',
    'Jin-seok', 'Sang-hyuk', 'Chul-soo', 'Gi-wang', 'Hyung-sik', 'Jae-joong', 'Kwang-soo', 'Min-soo', 'Se-young', 'Woong',
    'Yeon-seok', 'Beom-gyu', 'Dong-hae', 'G-dragon', 'Hwi-young', 'Jae-sang', 'Ji-seok', 'Jun-hyung', 'Kyu-hyun', 'Nam-woo',
    'San', 'Seung-min', 'Woo-sung', 'Yeon-jun', 'Byung-chul', 'Chang-sub', 'Do-young', 'Hee-won', 'Jae-wook', 'Jin-hwan',
    'Jung-shin', 'Min-sik', 'Ryeo-wook', 'Se-jun', 'Seung-yoon', 'Tae-joon', 'Won-woo', 'Young-min', 'Bong-seok', 'Dae-hwi',
    'Dong-joo', 'Geon-ho', 'Ha-sung', 'Jae-hwan', 'Kang-dae', 'Myung-dae', 'Sang-hun', 'Seung-cheol', 'Tae-seok', 'Yong-sun', 'Bo-seok',
    'Chang-wook', 'Dae-hyeon', 'Do-yoon', 'Hak-kun', 'Han-gyul', 'Han-sol', 'Ho-jin', 'Ho-sung', 'Hwan', 'Hyeon-jun',
    'Hyo-jong', 'Hyun-seung', 'Hyun-sik', 'Hyun-soo', 'Il-guk', 'Jae-beom', 'Jae-eun', 'Jae-min', 'Ji-hwan', 'Ji-sub',
    'Ji-tae', 'Ji-woong', 'Jin-ho', 'Jin-soo', 'Jong-up', 'Joon-gi', 'Joong-ki', 'Jung-hwan', 'Doyun', 'Siwoo',
    'Hajun', 'Eunwoo', 'Minjae', 'Jiho', 'Yujun', 'Yejun', 'Juwan', 'Seojun', 'Ian', 'Rowoon',
    'Subin', 'Donghyun', 'Gunwoo', 'Taeyang', 'Sunwoo', 'Jungwoo', 'Hyunwoo', 'Woojin', 'Jinu', 'Kangmin',
    'Minhyuk', 'Seungho', 'Jaehyun', 'Daehyun', 'Youngjae', 'Chanyeol', 'Baekhyun', 'Sehun'
]

FIRST_NAMES_MALE_RUSSIAN = [
    'Ivan', 'Dmitry', 'Alexey', 'Sergey', 'Andrey', 'Mikhail', 'Maxim', 'Artem', 'Daniil', 'Kirill',
    'Nikita', 'Ilya', 'Roman', 'Vladislav', 'Denis', 'Anton', 'Timur', 'Egor', 'Gleb', 'Pavel',
    'Konstantin', 'Oleg', 'Vadim', 'Viktor', 'Yury', 'Stanislav', 'Evgeny', 'Boris', 'Igor', 'Vyacheslav',
    'Leonid', 'Valery', 'Stepan', 'Fedor', 'Yaroslav', 'Gennady', 'Nikolay', 'Vitaly', 'Artur', 'Bogdan',
    'Matvey', 'Mark', 'Platon', 'Lev', 'Savely', 'David', 'Miron', 'Demid', 'Gordey', 'Semyon',
    'Anatoly', 'Arkady', 'Valentin', 'Grigory', 'Danila', 'Zakhar', 'Innokenty', 'Kuzma', 'Lavr', 'Makar',
    'Nazar', 'Ostap', 'Petr', 'Rodion', 'Svyatoslav', 'Taras', 'Filipp', 'Eduard', 'Yulian', 'Albert',
    'Bulat', 'Vsevolod', 'German', 'Demyan', 'Elisey', 'Ignat', 'Klim', 'Luka', 'Marat', 'Nestor',
    'Orest', 'Prokhor', 'Rinat', 'Spartak', 'Timofey', 'Ustyn', 'Fedot', 'Khariton', 'Yakov', 'Zinovy',
    'Aleksandr', 'Artyom', 'Maksim', 'Aleksey', 'Vladimir', 'Aleksei', 'Alexei', 'Andrei', 'Arseny', 'Georgy', 'Matvei',
    'Ruslan', 'Sergei', 'Timofei', 'Vasily', 'Yegor', 'Yuri', 'Artemiy', 'Zahar', 'Yuriy', 'Grigoriy',
    'Dmitriy', 'Evgeniy', 'Abram', 'Adam', 'Afanasiy', 'Akim', 'Anatoliy', 'Anisim', 'Antip', 'Apollon',
    'Aristarkh', 'Arkadiy', 'Arsen', 'Arseniy', 'Arkhip', 'Afanasy', 'Boleslav', 'Borya', 'Bronislav', 'Valeriy',
    'Varfolomey', 'Vasiliy', 'Venedikt', 'Veniamin', 'Vissarion', 'Vitaliy', 'Vlas', 'Vlad', 'Vladilen', 'Vladimir',
    'Vladlen', 'Vlas', 'Gavriil', 'Gavrila', 'Gennadiy', 'Georgiy', 'Gerasim', 'Danil', 'Dobrynya', 'Dorofey',
    'Evdokim', 'Evlampiy', 'Evlogiy', 'Evseviy', 'Evstafiy', 'Evstigney', 'Evstrat', 'Elizar', 'Emelyan', 'Epifan',
    'Eremiy', 'Ermolay', 'Erofeey', 'Efim', 'Efrem', 'Ignatiy'
]

FIRST_NAMES_MALE_THAI = [
    'Somchai', 'Thanawat', 'Kittisak', 'Supachai', 'Chanon', 'Natthaphon', 'Teerapat', 'Worawut', 'Peerawat', 'Kritsada',
    'Sirichai', 'Anan', 'Prasert', 'Arthit', 'Narong', 'Boonsri', 'Thongchai', 'Somkid', 'Chaiwat', 'Wittaya',
    'Phongsakorn', 'Thanaphat', 'Pongsak', 'Kasem', 'Chalerm', 'Sombat', 'Somkiat', 'Wichai', 'Prawit', 'Surachai',
    'Somporn', 'Wichit', 'Bunlue', 'Manit', 'Somboon', 'Nattawut', 'Suthep', 'Chatree', 'Kitti', 'Sakda',
    'Damrong', 'Chatchai', 'Piyawat', 'Anupong', 'Sarawut', 'Attaphol', 'Boonmee', 'Chaowalit', 'Danai', 'Ekarat',
    'Jirawat', 'Kamon', 'Mongkol', 'Niran', 'Paisan', 'Rachan', 'Sakchai', 'Tanakorn', 'Udom', 'Voravit',
    'Wachara', 'Yotsawat', 'Boonchu', 'Chaiporn', 'Decha', 'Ittiphol', 'Jaturong', 'Kittipong', 'Manop', 'Noppadol',
    'Pichai', 'Rungrot', 'Sanan', 'Taweesak', 'Uthai', 'Veera', 'Wanchai', 'Yanyong', 'Apichart', 'Boripat',
    'Chaiyaporn', 'Dusit', 'Ekachai', 'Jakkrit', 'Kobchai', 'Lert', 'Nattee', 'Panupong', 'Ritthichai', 'Sathit',
    'Theerasak', 'Wasan', 'Yongyuth', 'Adisak', 'Bancha', 'Charoen', 'Danupon', 'Ekapol', 'Jirayut', 'Kasidis',
    'Kriangkrai', 'Manat', 'Narongchai', 'Pakorn', 'Pipat', 'Prasit', 'Rattana', 'Sanit', 'Somsak', 'Suchart',
    'Suphat', 'Tawatchai', 'Thammarat', 'Theerayut', 'Thiti', 'Vichai', 'Wichan', 'Wisut', 'Woravit', 'Yongyut',
    'Amorn', 'Boonterm', 'Chavalit', 'Direk', 'Ekkarat', 'Jiraphat', 'Kamthorn', 'Kongkiat', 'Mana', 'Niphon',
    'Paitoon', 'Preecha', 'Rangsan', 'Sakol', 'Siri', 'Songpol', 'Suchin', 'Supot', 'Tawan', 'Thinnakorn',
    'Thongdee', 'Viroj', 'Wirote', 'Woraphon', 'Yuthana', 'Anucha', 'Boontong', 'Chatchawal', 'Ditsapong', 'Ittichai',
    'Akkharaphon', 'Anurak', 'Apisit', 'Athisit', 'Attasit', 'Banthit', 'Bawon', 'Benjaphon', 'Boonyarith', 'Chainarong',
    'Chakkraphan', 'Chalermchai', 'Chanwit', 'Charan', 'Chaturon', 'Chaweng', 'Chirayu', 'Chokchai', 'Damri', 'Danuphon',
    'Detnarong', 'Ekkaphon', 'Ekkasit', 'Intouch', 'Issara', 'Jaran', 'Jarun', 'Jetsada', 'Jirayus', 'Kanchit',
    'Kannaphat', 'Kanthaphon', 'Kasin', 'Kiatkrai', 'Kitsada', 'Kittithat', 'Komkrit', 'Konwit', 'Korapat', 'Kritsanaphon',
    'Manatsawin', 'Methee', 'Nakharin', 'Napat', 'Narakorn', 'Nattaphol', 'Nattasit', 'Nattavat', 'Navin', 'Nawaphon',
    'Nawin', 'Nithi', 'Nontawat', 'Nueng', 'Pakawat', 'Palat', 'Panat', 'Panuwat', 'Parinya', 'Pathom',
    'Peeradech', 'Phakphum', 'Phanuphong', 'Phanuwit', 'Phatsakon', 'Phawat', 'Philaphon', 'Phongsathorn', 'Phot', 'Phubet',
    'Phuwadon', 'Piti', 'Piyapong', 'Piyarat', 'Pongpat', 'Pongsathon', 'Pornchai', 'Pradit', 'Prateep', 'Preechaphon',
    'Rachanon', 'Rattapong', 'Rawat', 'Ronnachai', 'Rungroj', 'Saensuk', 'Saharat', 'Seksan', 'Kraisorn', 'Natthawut',
    'Phiraphon', 'Chanchai', 'Ekkachai', 'Panu', 'Sitthichai', 'Songkran', 'Sukrit', 'Teerawat', 'Thana', 'Thaworn',
    'Wisit', 'Yodchai', 'Apichat', 'Athis', 'Bandit', 'Kanok', 'Korn', 'Nattapong', 'Rangsikorn', 'Somphop',
    'Teerayut', 'Thanom', 'Thotsaphon', 'Warut', 'Anon', 'Boonsong', 'Chakkrit', 'Nattapol', 'Nirut', 'Pairoj',
    'Poom', 'Rattapoom', 'Saman', 'Santi', 'Sarit', 'Sinchai', 'Somnuek', 'Suksan', 'Surapol', 'Sutin',
    'Teerasak', 'Thanin', 'Tossaporn', 'Vanchai', 'Watcharapol', 'Wiwat', 'Yuttana', 'Akkarapol', 'Attapol', 'Booncherd',
    'Denchai', 'Kamron', 'Metha', 'Narin', 'Natthaphat', 'Pattarapol', 'Phichit', 'Piyanat', 'Prasop', 'Samroeng',
    'Santisuk', 'Sayam', 'Siriwat', 'Somrak', 'Songwit', 'Sumpun', 'Supanat', 'Surapong', 'Sutham', 'Thanakorn',
    'Thanapat', 'Thitiwat', 'Trairat', 'Vasant', 'Weerachai', 'Adisorn', 'Amnat', 'Anurat', 'Athiwat', 'Bounma',
    'Chaiyan', 'Chitsanupong', 'Dumrong', 'Jakkraphan', 'Kanit', 'Kovit', 'Nippon', 'Niti', 'Panlop', 'Peerapat',
    'Phithak', 'Pongsatorn', 'Pornthep', 'Rachata', 'Sakorn', 'Sarun', 'Siwakorn', 'Songwut', 'Supakorn', 'Suphot',
    'Surasit', 'Suwicha', 'Thanakrit', 'Tossapol', 'Watchara', 'Winai', 'Woraphot', 'Boonyarit', 'Ditsapon', 'Ekachart',
    'Itsara', 'Kiatisuk', 'Komsan', 'Nattaphon', 'Phasit', 'Rachanat', 'Adirak', 'Aphichat', 'Apinan', 'Arak', 'Aran',
    'Ariya', 'Arnont', 'Asadang', 'Atichat', 'Atipat', 'Atsawin', 'Benjarong', 'Boonchai', 'Boonlert', 'Boonma',
    'Boonserm', 'Boontam', 'Boontham', 'Boworn', 'Bunpot', 'Chaichan', 'Chaiyo', 'Chalit', 'Chalermpol', 'Chamlong',
    'Chamnan', 'Chanin', 'Chano', 'Charnvit', 'Charun', 'Chatri', 'Chawalit', 'Chedtha', 'Chen', 'Chetsada',
    'Chinda', 'Chirawat', 'Chit', 'Chon', 'Chongrak', 'Chotisak', 'Chuan', 'Chulalongkorn', 'Chumphon', 'Damnoen',
    'Danupat', 'Dechapol', 'Denpong', 'Detchart', 'Itthipat', 'Worawit', 'Wuttichai', 'Sompong', 'Bunchoo', 'Manas',
    'Nikorn', 'Thanet', 'Wichian', 'Chalong', 'Lek', 'Pairat', 'Tawat', 'Wirot'
]

FIRST_NAMES_MALE_WESTERN = [
    'Liam', 'Noah', 'Oliver', 'James', 'Elijah', 'William', 'Henry', 'Lucas', 'Benjamin', 'Theodore',
    'Mateo', 'Levi', 'Sebastian', 'Daniel', 'Jack', 'Alexander', 'Owen', 'Asher', 'Samuel', 'Ethan',
    'John', 'David', 'Joseph', 'Matthew', 'Luke', 'Julian', 'Leo', 'Gabriel', 'Anthony', 'Dylan',
    'Thomas', 'Isaac', 'Christopher', 'Joshua', 'Andrew', 'Nathan', 'Ryan', 'Adrian', 'Christian', 'Aaron',
    'Eli', 'Colton', 'Luca', 'Landon', 'Hunter', 'Jonathan', 'Nolan', 'Connor', 'Jeremiah', 'Ezekiel',
    'Nicholas', 'Austin', 'Tyler', 'Brandon', 'Kevin', 'Justin', 'Jason', 'Brian', 'Zachary', 'Eric',
    'Adam', 'Jacob', 'Mason', 'Logan', 'Aiden', 'Jackson', 'Michael', 'Caleb', 'Isaiah', 'Charles',
    'Josiah', 'Cameron', 'Carson', 'Robert', 'Angel', 'Miles', 'Jordan', 'Dominic', 'Greyson', 'Ian',
    'Elias', 'Jaxson', 'Jose', 'Evan', 'Maverick', 'Bryson', 'Jace', 'Cooper', 'Xavier', 'Parker',
    'Roman', 'Santiago', 'Chase', 'Sawyer', 'Gavin', 'Leonardo', 'Kayden', 'Ayden', 'Jameson', 'Everett',
    'Axel', 'Easton', 'Bentley', 'Damian', 'Kingston', 'Harrison', 'Cole', 'Declan', 'Weston', 'Silas',
    'Bennett', 'Arthur', 'Jasper', 'Theo', 'George', 'Max', 'Finn', 'Diego', 'Paul', 'Mark',
    'Kenneth', 'Steven', 'Edward', 'Ronald', 'Timothy', 'Jeffrey', 'Gary', 'Frank', 'Raymond', 'Patrick',
    'Gregory', 'Dennis', 'Jerry', 'Peter', 'Walter', 'Harold', 'Douglas', 'Carl', 'Terry', 'Sean',
    'Keith', 'Joe', 'Jesse', 'Willie', 'Billy', 'Bryan', 'Albert', 'Wayne', 'Roy', 'Ralph',
    'Eugene', 'Louis', 'Harry', 'Randy', 'Howard', 'Fred', 'Philip', 'Alan', 'Danny', 'Stanley',
    'Leonard', 'Nathaniel', 'Martin', 'Craig', 'Victor', 'Phillip', 'Todd', 'Ernest', 'Shawn', 'Clarence',
    'Norman', 'Darren', 'Brett', 'Kurt', 'Derek', 'Cory', 'Neil', 'Troy', 'Dustin', 'Shane',
    'Lance', 'Cody', 'Travis', 'Seth', 'Trevor', 'Spencer', 'Garrett', 'Brent', 'Russell', 'Clayton',
    'Mitchell', 'Ezra', 'Hudson', 'Jaxon', 'Jayden', 'Lincoln', 'Wyatt', 'Aidan', 'Alec', 'Alex',
    'Alfred', 'Allen', 'Andre', 'Antonio', 'Barry', 'Beau', 'Ben', 'Grayson', 'Carter', 'Kai',
    'Micah', 'Brooks', 'Alonzo', 'Andy', 'Ashton', 'Austen', 'Barrett', 'Benson', 'Blaine', 'Blake', 'Bradley',
    'Brady', 'Brantley', 'Braxton', 'Brendan', 'Brennan', 'Brock', 'Brody', 'Bruce', 'Bryce', 'Byron',
    'Cade', 'Caden', 'Callum', 'Calvin', 'Carlos', 'Casey', 'Cedric', 'Chad', 'Chance', 'Chandler',
    'Chester', 'Chris', 'Clark', 'Clay', 'Clifford', 'Clint', 'Clinton', 'Colby', 'Colin', 'Collin',
    'Colt', 'Conner', 'Conor', 'Conrad', 'Corbin', 'Corey', 'Waylon', 'Brooks', 'Wesley', 'Walker',
    'Rowan', 'August', 'River', 'Amir', 'Enzo', 'Gael', 'Emmett', 'Myles', 'Maxwell', 'Dean',
    'Karter', 'Calum', 'Ryker', 'Zion', 'Abel', 'Leon', 'Zane', 'Tristan', 'Graham', 'Luka',
    'Hayden', 'Ronan', 'Jude', 'Grant', 'Richard', 'Beckett', 'Archer', 'Holden', 'Felix', 'Nicolas',
    'Dallas', 'Preston', 'Jeremy', 'Joel', 'Kaden', 'Maddox', 'Marcus', 'Simon', 'Tate', 'Dawson',
    'Lane', 'Tucker', 'Gideon', 'Knox', 'Milo', 'Nash', 'Rhys', 'Kash', 'Finley', 'Rhett',
    'Dalton', 'Cash', 'Ellis', 'Ace', 'Alonzo', 'Alvin', 'Amos', 'Anderson', 'Apollo', 'Ari',
    'Arlo', 'Armando', 'Arnold', 'Arturo', 'Atlas', 'Atticus', 'Augustus', 'Avery', 'Baker', 'Baron',
    'Beck', 'Bellamy', 'Blaise', 'Bo', 'Bodhi', 'Bowen', 'Braden', 'Braylen', 'Braylon', 'Bruno',
    'Caiden', 'Cain', 'Cairo', 'Callan', 'Camden', 'Cannon', 'Cassian', 'Cesar', 'Chaim', 'Coby',
    'Cohen', 'Corban', 'Crosby', 'Cruz', 'Curtis', 'Cyrus', 'Dakota', 'Damien', 'Damon', 'Dane',
    'Dante', 'Darian', 'Darius', 'Dash', 'Davis', 'Deandre', 'Derrick', 'Deshawn', 'Devin', 'Dexter',
    'Dillon', 'Dominick', 'Donald', 'Donovan', 'Dorian', 'Drake', 'Drew', 'Duke', 'Dwayne', 'Edgar',
    'Edmund', 'Edwin', 'Elian', 'Eliseo', 'Elliot', 'Elliott', 'Emanuel', 'Emerson', 'Emilio', 'Emmanuel',
    'Erik', 'Ernesto', 'Esteban', 'Fabian', 'Fisher', 'Fletcher', 'Flynn', 'Forrest', 'Foster', 'Francis',
    'Francisco', 'Franco', 'Franklin', 'Frederick', 'Gage', 'Gerard', 'Gerardo', 'Gian', 'Gibson', 'Gilbert',
    'Giovanni', 'Gordon', 'Grady', 'Granger', 'Griffin', 'Gunnar', 'Gunner', 'Gustavo', 'Hank', 'Harlan',
    'Harley', 'Harvey', 'Hayes', 'Heath', 'Hector', 'Henrik', 'Hezekiah', 'Houston', 'Hugh', 'Hugo',
    'Ibrahim', 'Ignacio', 'Ingram', 'Izaiah', 'Jaden', 'Jadiel', 'Jair', 'Jalen', 'Jamal', 'Jamie',
    'Jared', 'Jarrod', 'Jarvis', 'Jayson', 'Jensen', 'Jerome', 'Jimmy', 'Joaquin', 'Johnathan', 'Johnny',
    'Jonas', 'Jordi', 'Jorge', 'Josue', 'Jovanni', 'Juan', 'Judah', 'Julius', 'Junior', 'Justice',
    'Kade', 'Kaiden', 'Kaleb', 'Kameron', 'Kane', 'Kareem', 'Karson', 'Kason', 'Keanu', 'Keaton',
    'Keegan', 'Kellen', 'Kelvin', 'Kendrick', 'Kenny', 'Kieran', 'Killian', 'King', 'Kingsley', 'Kody',
    'Kolton', 'Korbin', 'Krew', 'Kyle', 'Kyler', 'Kyree', 'Lachlan', 'Landen', 'Larry', 'Lawrence',
    'Lawson', 'Layton', 'Ledger', 'Lee', 'Legend', 'Leland', 'Lennon', 'Lennox', 'Leonel', 'Leopold',
    'Leroy', 'Lewis', 'Linus', 'Lionel', 'Luciano', 'Lucien', 'Lukas', 'Lyle', 'Mac', 'Mack',
    'Malachi', 'Malakai', 'Malcolm', 'Malik', 'Manuel', 'Marc', 'Marcel', 'Marcelo', 'Marco', 'Marcos',
    'Mario', 'Markus', 'Marshall', 'Marvin', 'Mathew', 'Mathias', 'Matias', 'Matteo', 'Maurice', 'Mauricio',
    'Maximiliano', 'Maximus', 'McCall', 'Mekhi', 'Melvin', 'Memphis', 'Milan', 'Miller', 'Milton', 'Misael',
    'Mohamed', 'Mohammad', 'Morgan', 'Moses', 'Muhammad', 'Murphy', 'Nehemiah', 'Nelson', 'Nico', 'Nigel',
    'Niko', 'Noel', 'Oakley', 'Odin', 'Omar', 'Orion', 'Orlando', 'Orson', 'Oscar', 'Otto',
    'Pablo', 'Palmer', 'Paxton', 'Pedro', 'Perry', 'Peyton', 'Phoenix', 'Pierce', 'Porter', 'Prince',
    'Princeton', 'Quentin', 'Quincy', 'Rafael', 'Raiden', 'Ramon', 'Ramsey', 'Raphael', 'Raul', 'Ray',
    'Raylan', 'Reed', 'Reese', 'Reginald', 'Remington', 'Remy', 'Rene', 'Reuben', 'Rex', 'Ricardo',
    'Ricky', 'Ridge', 'Riley', 'Rocco', 'Roderick', 'Rodney', 'Roger', 'Rogelio', 'Roland', 'Rory',
    'Ross', 'Royce', 'Ruben', 'Rudy', 'Ryder', 'Rylan', 'Sage', 'Samson', 'Santino', 'Saul',
    'Scott', 'Sergio', 'Shaun', 'Shepard', 'Shepherd', 'Shiloh', 'Sincere', 'Skyler', 'Solomon', 'Soren',
    'Stefan', 'Stephen', 'Sterling', 'Stetson', 'Sullivan', 'Sutton', 'Sylvester', 'Talon', 'Tanner', 'Tatum',
    'Taylor', 'Terrance', 'Terrell', 'Terrence', 'Thaddeus', 'Thatcher', 'Titus', 'Tobias', 'Toby', 'Tommy',
    'Tony', 'Trace', 'Trent', 'Trenton', 'Trey', 'Truman', 'Turner', 'Ty', 'Tyson', 'Ulises',
    'Uriah', 'Uriel', 'Vance', 'Vaughan', 'Vicente', 'Vince', 'Vincent', 'Vincenzo', 'Wade', 'Wallace',
    'Warren', 'Watson', 'Wells', 'Wes', 'Westin', 'Wilder', 'Will', 'Wilson', 'Winston', 'Xander',
    'Zachariah', 'Zaid', 'Zaiden', 'Zayn', 'Zayne', 'Zechariah', 'Zeke', 'Alfie', 'Archie', 'Freddie',
    'Charlie', 'Teddy', 'Albie', 'Jenson', 'Ronnie', 'Reggie', 'Bobby', 'Sonny', 'Frankie', 'Louie',
    'Otis', 'Finlay', 'Fraser', 'Alistair', 'Alastair', 'Angus', 'Brogan', 'Callen', 'Ciaran', 'Cormac',
    'Duncan', 'Euan', 'Ewan', 'Fergus', 'Fionn', 'Gareth', 'Hamish', 'Iain', 'Keir', 'Lorcan',
    'Magnus', 'Murdo', 'Murray', 'Niall', 'Ramsay', 'Stewart', 'Stuart', 'Gethin', 'Griffith', 'Gwilym',
    'Hywel', 'Ieuan', 'Iwan', 'Llewellyn', 'Macsen', 'Osian', 'Owain', 'Rhodri', 'Sion', 'Steffan',
    'Tudur',
]

HO_VIET = [
    'Nguyễn', 'Trần', 'Lê', 'Phạm', 'Hoàng', 'Huỳnh', 'Phan', 'Vũ', 'Võ', 'Đặng',
    'Bùi', 'Đỗ', 'Hồ', 'Ngô', 'Dương', 'Lý', 'Đinh', 'Đoàn', 'Lâm', 'Mai',
    'Trịnh', 'Đào', 'Cao', 'Hà', 'Lưu', 'Lương', 'Thái', 'Châu', 'Tạ', 'Phùng',
    'Tô', 'Vương', 'Tăng', 'Quách', 'Nhan', 'Kiều', 'Triệu', 'Hứa', 'Nghiêm', 'Chu',
    'Tống', 'Diệp', 'Lại', 'Từ', 'Trương', 'Tôn'
]

LAST_NAMES_ARABIC = [
    'Al-Mansoor', 'Al-Harbi', 'Al-Ghamdi', 'Al-Otaibi', 'Al-Shehri', 'Al-Zahrani', 'Al-Dossari', 'Al-Mutairi', 'Al-Qahtani', 'Al-Anzi',
    'Al-Rashid', 'Al-Sayed', 'Al-Najjar', 'Al-Khatib', 'Al-Hassan', 'Al-Masri', 'Al-Shami', 'Al-Ali', 'Al-Saleh', 'Al-Ahmad',
    'Al-Mahmoud', 'Al-Sulaiman', 'Al-Khalil', 'Al-Hamad', 'Al-Subaie', 'Al-Marri', 'Al-Hajri', 'Al-Ajmi', 'Al-Kuwari', 'Al-Thani',
    'Al-Nuaimi', 'Al-Balushi', 'Al-Farsi', 'Al-Jabri', 'Al-Zaabi', 'Al-Kaabi', 'Al-Hosani', 'Al-Dhaheri', 'Al-Remeithi', 'Al-Ketbi',
    'Al-Mazrouei', 'Al-Suwaidi', 'Al-Falasi', 'Al-Maktoum', 'Al-Qasimi', 'Al-Sharqi', 'Al-Mualla', 'Al-Nuaim', 'Al-Binali', 'Al-Tamimi',
    'Al-Omari', 'Al-Badr', 'Al-Fayez', 'Al-Qadi', 'Al-Sabah', 'Al-Khalifa', 'Al-Hashimi', 'Al-Madani', 'Al-Gailani', 'Al-Idrisi',
    'Al-Jawad', 'Al-Kazemi', 'Al-Lami', 'Al-Musawi', 'Al-Najafi', 'Al-Quraishi', 'Al-Rifai', 'Al-Samarraie', 'Al-Tikriti', 'Al-Ward',
    'Al-Zubaidi', 'Al-Askari', 'Al-Bayati', 'Al-Darwish', 'Al-Farooqi', 'Al-Ghanem', 'Al-Hakim', 'Al-Jazairi', 'Al-Khafaji', 'Al-Lahham',
    'Al-Shammari', 'Al-Amri', 'Al-Hazmi', 'Al-Bishi', 'Al-Nahyan', 'Abbasi', 'Abdallah', 'Abdelnour', 'Abdul', 'Abed', 'Abu',
    'Al-Amin', 'Al-Ansari', 'Al-Badawi', 'Al-Bahar', 'Al-Bakr', 'Al-Din', 'Al-Fassi', 'Al-Habib', 'Al-Haddad', 'Al-Halabi',
    'Al-Kurdi', 'Al-Mutawa', 'Al-Qasim', 'Al-Saad', 'Al-Sharif', 'Al-Zahra', 'Al-Zaidi', 'Alam', 'Ali', 'Amin',
    'Amir', 'Asghar', 'Ashraf', 'Attar', 'Awad', 'Ayyad', 'Badawi', 'Bakir', 'Barakat', 'Basha',
    'Bitar', 'Boulos', 'Chahine', 'Al-Qarni', 'Al-Anazi', 'Al-Ruwaili', 'Al-Sahli', 'Al-Husseini', 'Al-Nahyan', 'Abboud',
    'Abdo', 'Abdou', 'Abiad', 'Abou', 'Abou-Chakra', 'Abou-Khalil', 'Abou-Nader', 'Abou-Rizk', 'Abou-Samra', 'Acar',
    'Achkar', 'Adas', 'Adra', 'Agha', 'Ahmad', 'Ahmed', 'Ajami', 'Akel', 'Akiki', 'Akkar',
    'Akl', 'Al-Abdallah', 'Al-Amoudi', 'Al-Arab', 'Al-Asad', 'Al-Assaf', 'Al-Attar', 'Al-Azm', 'Al-Bader', 'Al-Barazi',
    'Al-Basha', 'Al-Bitar', 'Al-Boustani', 'Al-Dabbagh', 'Al-Dahhan', 'Al-Dakheel', 'Al-Dayeh', 'Al-Fahad', 'Al-Faisal', 'Al-Faraj',
    'Al-Farhan', 'Al-Ghazali', 'Al-Habash', 'Al-Hafiz', 'Al-Hamdan', 'Al-Hammadi', 'Al-Homsi', 'Al-Hussein', 'Al-Ibrahim', 'Al-Idrissi',
    'Al-Issa', 'Al-Jamil', 'Al-Jarrah', 'Al-Jassim', 'Al-Jundi', 'Al-Kadri', 'Al-Kafri', 'Al-Kahale', 'Al-Kallas', 'Al-Karam',
    'Al-Kassem', 'Al-Kayali', 'Al-Khoury', 'Al-Kilani', 'Al-Koussa', 'Al-Kurd'
]

LAST_NAMES_BRAZILIAN = [
    'Silva', 'Santos', 'Oliveira', 'Souza', 'Rodrigues', 'Ferreira', 'Alves', 'Pereira', 'Lima', 'Gomes',
    'Costa', 'Ribeiro', 'Martins', 'Carvalho', 'Almeida', 'Lopes', 'Soares', 'Fernandes', 'Vieira', 'Barbosa',
    'Rocha', 'Dias', 'Nascimento', 'Andrade', 'Moreira', 'Nunes', 'Marques', 'Machado', 'Mendes', 'Freitas',
    'Cardoso', 'Ramos', 'Goncalves', 'Santana', 'Teixeira', 'Araujo', 'Moura', 'Cavalcanti', 'Pinto', 'Castro',
    'Campos', 'Monteiro', 'Barros', 'Moraes', 'Dantas', 'Figueiredo', 'Farias', 'Miranda', 'Borges', 'Neves',
    'Azevedo', 'Brito', 'Coutinho', 'Duarte', 'Esteves', 'Fagundes', 'Guedes', 'Henrique', 'Inacio', 'Jardim',
    'Lacerda', 'Macedo', 'Nogueira', 'Ornelas', 'Peixoto', 'Queiroz', 'Resende', 'Sampaio', 'Tavares', 'Uchoa',
    'Valente', 'Xavier', 'Zambrano', 'Aguiar', 'Batista', 'Correia', 'Drummond', 'Espindola', 'Fontes', 'Gouveia',
    'Abranches', 'Abreu', 'Affonso', 'Afonso', 'Agostinho', 'Aires', 'Albuquerque', 'Alcantara', 'Aleixo', 'Alencar',
    'Alexandre', 'Alfradique', 'Alvarenga', 'Alvares', 'Alvim', 'Amaral', 'Amato', 'Ambrozio', 'Amorim', 'Anchieta',
    'Andrada', 'Antas', 'Antonialli', 'Antunes', 'Apparecido', 'Aquino', 'Aragao', 'Arantes', 'Arcanjo', 'Areias',
    'Arruda', 'Assis', 'Assuncao', 'Athayde', 'Avancini', 'Avelar', 'Avelino', 'Avila', 'Azambuja', 'Bacellar',
    'Badaro', 'Baeta', 'Bahia', 'Balbino', 'Baltazar', 'Baptista', 'Barata', 'Barcellos', 'Barcelos', 'Barcellos',
    'Barra', 'Barreira', 'Barreto', 'Barroso', 'Bastos', 'Bazan', 'Belfort', 'Belisario', 'Bellini', 'Belmonte',
    'Belo', 'Beltrao', 'Benevides', 'Benicio', 'Bentes', 'Bento', 'Berenguer', 'Bernardino', 'Bernardo', 'Bernardi',
    'Bertolucci', 'Bessa', 'Betencourt', 'Bezerra', 'Bianchi', 'Bicalho', 'Bicalho', 'Bittencourt', 'Boaventura', 'Bocaiuva',
    'Bocanera', 'Borja', 'Botelho', 'Braga', 'Braganca'
]

LAST_NAMES_CHINESE = [
    'Wang', 'Li', 'Zhang', 'Liu', 'Chen', 'Yang', 'Huang', 'Zhao', 'Wu', 'Zhou',
    'Xu', 'Sun', 'Ma', 'Zhu', 'Hu', 'Guo', 'He', 'Gao', 'Lin', 'Luo',
    'Zheng', 'Liang', 'Xie', 'Song', 'Tang', 'Han', 'Feng', 'Deng', 'Cao', 'Peng',
    'Zeng', 'Xiao', 'Tian', 'Dong', 'Yuan', 'Pan', 'Yu', 'Jiang', 'Cai', 'Du',
    'Ye', 'Cheng', 'Su', 'Wei', 'Lu', 'Ding', 'Ren', 'Shen', 'Yao', 'Cui',
    'Zhong', 'Tan', 'Fan', 'Jin', 'Shi', 'Liao', 'Jia', 'Xia', 'Fu', 'Fang',
    'Bai', 'Zou', 'Meng', 'Xiong', 'Qin', 'Qiu', 'Yin', 'Xue', 'Yan', 'Duan',
    'Lei', 'Hou', 'Long', 'Tao', 'Mao', 'Hao', 'Gu', 'Gong', 'Shao', 'Wan',
    'Qian', 'Lai', 'Hong', 'An', 'Chang', 'Kang', 'Niu', 'Geng', 'Ji', 'Mo',
    'Chai', 'Kong', 'Xiang', 'Qi', 'Yue', 'Bi', 'Bian', 'Chu', 'Mu', 'Zhuang',
    'Pu', 'Yi', 'Qu', 'Zan', 'Sha', 'Sang', 'Bao', 'Che', 'Di', 'Fei',
    'Ge', 'Hua', 'Jiao', 'Kuang', 'Lian', 'Mei', 'Nie', 'Ouyang', 'Pang', 'Qiao',
    'Rong', 'Shang', 'Tong', 'Weng', 'Xi', 'You', 'Zhan', 'Aisin', 'Bo', 'Chao',
    'Duanmu', 'Fucha', 'Guan', 'Helan', 'Huangfu', 'Jing', 'Leduo', 'Murong', 'Bu', 'Cen',
    'Chi', 'Dai', 'Dang', 'Diao', 'Dou', 'Gai', 'Gan', 'Gou', 'Hai', 'Hei',
    'Huo', 'Jian', 'Jiu', 'Ju', 'Ke', 'Kou', 'Kuai', 'Kui', 'Lan', 'Lang',
    'Lao', 'Leng', 'Ling', 'Lou', 'Luan', 'Lv', 'Ruan', 'Sheng', 'Wen', 'Xing',
    'Zong', 'Bie', 'Ou', 'Shan', 'Tu', 'Zhuo', 'Zuo', 'Gui', 'Chun', 'Guang', 'Huan',
    'Ba', 'Bing', 'Can', 'Chong', 'Chuan', 'Ci', 'Cong', 'Da', 'Dan', 'Dao',
    'De', 'Dian', 'Duo', 'E', 'Er', 'Fa', 'Fen', 'Gang', 'Gen', 'Gua',
    'Heng', 'Hui', 'Juan', 'Jun', 'Kai', 'Kan', 'Kao', 'Ku', 'Sima', 'Shangguan',
    'Zhuge', 'Dugu', 'Yuchi', 'Tantai', 'Gongsun', 'Baili', 'Dongfang', 'Nangong', 'Ximen', 'Beigong',
    'Chunyu', 'Xuanmian', 'Sikong', 'Situ', 'Zongzheng'
]

LAST_NAMES_FILIPINO = [
    'Santos', 'Reyes', 'Cruz', 'Bautista', 'Ocampo', 'Garcia', 'Mendoza', 'Torres', 'Tomas', 'Andrada',
    'Ramos', 'Flores', 'Castro', 'Rivera', 'Aquino', 'Navarro', 'Salazar', 'Mercado', 'Dela Cruz', 'Del Rosario',
    'Fernandez', 'Lopez', 'Villanueva', 'Santiago', 'Castillo', 'De Leon', 'Magno', 'Valenzuela', 'Pascual', 'Soriano',
    'Manalo', 'Tolentino', 'Morales', 'Miranda', 'Padilla', 'Domingo', 'Gomez', 'Concepcion', 'Aguilar', 'Estrada',
    'Perez', 'Velasco', 'Alvarez', 'Corpuz', 'Sarmiento', 'Geronimo', 'Ilagan', 'Lagman', 'Mallari', 'Natividad',
    'Atienza', 'Cortez', 'Delos Reyes', 'Ignacio', 'Bernardo', 'Espiritu', 'Magbanua', 'Panganiban', 'Quizon', 'Roxas',
    'Tinio', 'Umali', 'Valdez', 'Yambao', 'Zamora', 'Abad', 'Beltran', 'Capulong', 'Dimayuga', 'Enriquez',
    'Fabian', 'Guerrero', 'Hilario', 'Imperial', 'Javier', 'Abalos', 'Abarca', 'Abella', 'Abellana', 'Abello',
    'Ablan', 'Abreu', 'Abril', 'Absalon', 'Acero', 'Acosta', 'Acuna', 'Adrias', 'Agoncillo', 'Agpaoa',
    'Aguas', 'Agudo', 'Aguila', 'Aguinaldo', 'Aguirre', 'Agustin', 'Alano', 'Alarcon', 'Alba', 'Albano',
    'Alberto', 'Alcala', 'Alcantara', 'Alcazar', 'Alcid', 'Aldaba', 'Alegre', 'Alejandro', 'Alfaro', 'Alfonso',
    'Alimurung', 'Alip', 'Almeda', 'Almonte', 'Alonzo', 'Altamirano', 'Amador', 'Amante', 'Amor', 'Amorsolo',
    'Ampil', 'Ancheta', 'Andal', 'Andaya', 'Andres', 'Angeles', 'Angara', 'Aniceto', 'Antonio', 'Aparicio',
    'Apostol', 'Aragon', 'Araneta', 'Arante', 'Arce', 'Arceo', 'Arcilla', 'Arellano', 'Arenas', 'Arevalo',
    'Arguelles', 'Arias', 'Arienda', 'Arnaiz', 'Aromin', 'Arostegui', 'Arrieta', 'Arroyo', 'Artiaga', 'Artigas',
    'Asenjo', 'Asis', 'Aspiras', 'Astorga', 'Asuncion', 'Atilano', 'Aurelio', 'Austria', 'Avellana', 'Avila',
    'Ayala', 'Azurin', 'Babao', 'Bacani', 'Badillo', 'Bagatsing', 'Balagtas', 'Balane', 'Balatbat', 'Balboa'
]

LAST_NAMES_INDIAN = [
    'Sharma', 'Verma', 'Gupta', 'Singh', 'Kumar', 'Patel', 'Shah', 'Joshi', 'Nair', 'Rao',
    'Reddy', 'Yadav', 'Das', 'Mishra', 'Bhat', 'Mehta', 'Iyer', 'Banerjee', 'Chatterjee', 'Mukherjee',
    'Dutta', 'Sengupta', 'Roy', 'Bose', 'Chakraborty', 'Sen', 'Ghosh', 'Agarwal', 'Bansal', 'Mittal',
    'Goyal', 'Jindal', 'Singhal', 'Garg', 'Goel', 'Jain', 'Maheshwari', 'Khandelwal', 'Chauhan', 'Rajput',
    'Rathore', 'Parmar', 'Solanki', 'Tomar', 'Rawat', 'Bisht', 'Negi', 'Pandey', 'Tiwari', 'Shukla',
    'Dubey', 'Chaubey', 'Tripathi', 'Upadhyay', 'Pathak', 'Dwivedi', 'Saxena', 'Srivastava', 'Bhatnagar', 'Mathur',
    'Kulshrestha', 'Johari', 'Nigam', 'Kapoor', 'Khanna', 'Malhotra', 'Chopra', 'Dhawan', 'Bhatia', 'Arora',
    'Anand', 'Grover', 'Sahni', 'Sethi', 'Suri', 'Tandon', 'Vohra', 'Chawla', 'Ahuja', 'Juneja',
    'Batra', 'Wadhwa', 'Gandhi', 'Modi', 'Desai', 'Parekh', 'Trivedi', 'Bhatt', 'Dave', 'Pandya',
    'Merchant', 'Somani', 'Lodha', 'Birla', 'Rungta', 'Dhoot', 'Ambani', 'Tata', 'Godrej', 'Bajaj',
    'Mahindra', 'Murthy', 'Pillai', 'Menon', 'Nambiar', 'Kurup', 'Panicker', 'Varman', 'Naidu', 'Choudhary',
    'Goud', 'Shetty', 'Hegde', 'Pai', 'Kamath', 'Prabhu', 'Shenoy', 'Naik', 'Kulkarni', 'Deshpande',
    'Patil', 'Pawar', 'Jadhav', 'Shinde', 'Bhosale', 'Kadam', 'Gaekwad', 'Chavan', 'Sawant', 'More',
    'Bhave', 'Kelkar', 'Apte', 'Gokhale', 'Ranade', 'Tilak', 'Paranjpe', 'Modak', 'Karve', 'Gadgil',
    'Bendre', 'Sane', 'Kanitkar', 'Deodhar', 'Limaye', 'Puntambekar', 'Abhyankar', 'Chiplunkar', 'Godbole', 'Karkhanis',
    'Phadke', 'Sahasrabuddhe', 'Vaidya', 'Wagle', 'Agarkar', 'Chitnis', 'Dandekar', 'Gore', 'Hate', 'Inamdar',
    'Acharya', 'Aggarwal', 'Ahluwalia', 'Bakshi', 'Balakrishnan', 'Bandopadhyay', 'Basu', 'Bhandari', 'Bhardwaj', 'Bhargava',
    'Bhattacharya', 'Bora', 'Chaudhuri', 'Chettiar', 'Deshmukh', 'Devar', 'Dhaliwal', 'Dhar', 'Dhingra', 'Ganesan',
    'Ganguly', 'Gautam', 'Ghoshal', 'Goswami', 'Govindarajan', 'Grewal', 'Gujral', 'Kalyan', 'Kannan', 'Kashyap',
    'Kaul', 'Kaur', 'Khatri', 'Kohli', 'Krishnan', 'Majumdar', 'Malik', 'Mallick', 'Mandal', 'Manian',
    'Marathe', 'Namboodiri', 'Narayan', 'Narayanaswamy', 'Natarajan', 'Nayak', 'Padmanabhan', 'Pandit', 'Parashar', 'Prasad',
    'Puri', 'Radhakrishnan', 'Raghunathan', 'Rajan', 'Rajagopal', 'Raman', 'Ramanathan', 'Ramaswamy', 'Ranganathan', 'Rastogi',
    'Sabharwal', 'Sachdev', 'Sahay', 'Sandhu', 'Sarabhai', 'Sarin', 'Sastry', 'Sathe', 'Sehgal', 'Sethuraman',
    'Shroff', 'Sidhu', 'Soman', 'Soundararajan', 'Srinivasan', 'Subramanian', 'Sundaram', 'Swaminathan', 'Talwar', 'Choudhury',
    'Dey', 'Sarkar', 'Pal', 'Mondal', 'Biswas', 'Nandy', 'Saha', 'Mitra', 'Kundu', 'Bhowmick',
    'Kar', 'Basak', 'Halder', 'Paul', 'Bagchi', 'Adhikari', 'Barman', 'Karmakar', 'Pramanik', 'Samanta',
    'Santra', 'Naskar', 'Sardar', 'Laha', 'Kole', 'Bhunia', 'Guchhait', 'Midya', 'Manna', 'Rana',
    'Panja', 'Sasmal', 'Giri', 'Hazra', 'Patra', 'Bera', 'Jana', 'Dasgupta', 'Moitra', 'Lahiri',
    'Sanyal', 'Bag', 'Roychowdhury', 'Debnath', 'Baidya', 'Sikdar', 'Majhi', 'Bauri', 'Ruidas', 'Bagdi',
    'Lohar', 'Ankure', 'Mete', 'Dom', 'Muchi', 'Dhara', 'Mal', 'Konar', 'Gayen', 'Kayal',
    'Purkait', 'Gharami', 'Laskar', 'Molla', 'Sekh', 'Gazi', 'Paik', 'Haldar', 'Mistri', 'Kandar',
    'Bayen', 'Dhali', 'Midday', 'Bar', 'Naiya', 'Howladar', 'Gain', 'Ghoroi', 'Dolui', 'Maity',
    'Barik', 'Khatua', 'Ghorai', 'Bhowmik', 'Guria', 'Mahapatra', 'Panda', 'Tripathy', 'Mohanty', 'Behera',
    'Sahoo', 'Sahu', 'Pradhan', 'Jena', 'Rout', 'Swain', 'Satapathy', 'Dash', 'Padhi', 'Samal',
    'Ojha', 'Parida', 'Bhoi', 'Biswal', 'Muduli', 'Lenka', 'Khandei', 'Behuria', 'Dalai', 'Dalei',
    'Senapati', 'Sethy', 'Tarai', 'Dehury', 'Pruseth', 'Khuntia', 'Badajena', 'Kanhar', 'Kuanr', 'Bagha',
    'Srichandan', 'Harichandan', 'Jagadev', 'Mardaraj', 'Samantsinghar', 'Ray', 'Patnaik', 'Chhotaray', 'Bahinipati', 'Samantray',
    'Paikaray', 'Champatiray', 'Mansingh', 'Routray', 'Baliarsingh', 'Uttarsingh', 'Sundarray', 'Mangaraj', 'Dakua', 'Bisoi',
    'Gouda', 'Subudhi', 'Prusty', 'Maharana', 'Bindhani', 'Kamila', 'Sutar', 'Moharana', 'Rupashree', 'Agrawal',
    'Altekar', 'Ambedkar', 'Ansari', 'Arya', 'Bajpai', 'Balasubramanian', 'Bapat', 'Bedi', 'Bhopatkar', 'Bindra',
    'Chadha', 'Chandra', 'Chaturvedi', 'Chaudhary', 'Chhabra', 'Dange', 'Dikshit', 'Dixit', 'Gangopadhyay', 'Ghatak',
    'Ghosal', 'Gulati', 'Guptan', 'Iyengar', 'Jaishankar', 'Kirloskar', 'Adiga', 'Agashe', 'Agnihotri', 'Ahir', 'Alva',
    'Ambekar', 'Aras', 'Athalye', 'Athavale', 'Atre', 'Babbar', 'Bachchan', 'Badami', 'Bahuguna', 'Baid',
    'Bailur', 'Bains', 'Bairagi', 'Balaji', 'Balan', 'Baliga', 'Balsavar', 'Barad', 'Barde', 'Barve',
    'Batish', 'Baveja', 'Behl', 'Belavadi', 'Belvalkar', 'Benegal', 'Bhaduri', 'Bhagat', 'Bhalla', 'Bhandarkar',
    'Bhargav', 'Bhatkhande', 'Bhavsar', 'Bhende', 'Bhide', 'Bidnur', 'Bijoor', 'Biyani', 'Bobde', 'Bodas',
    'Borwankar', 'Brahmbhatt', 'Brijwasi', 'Burman', 'Chakravarti', 'Chander', 'Chandiramani', 'Chandrachud', 'Chandran', 'Charan',
    'Chhatwal', 'Chhina', 'Chidambaram', 'Chitre', 'Choksi', 'Chouhan', 'Dadabhoy', 'Dadhich', 'Dalvi', 'Dambal',
    'Darak', 'Darda', 'Datar', 'Date', 'Dattagupta', 'Davuluri', 'Deol', 'Devadiga', 'Deval', 'Thakur'
]

LAST_NAMES_INDONESIAN = [
    'Wijaya', 'Saputra', 'Pratama', 'Santoso', 'Setiawan', 'Kusuma', 'Hidayat', 'Nugroho', 'Utomo', 'Wibowo',
    'Kurniawan', 'Gunawan', 'Susanto', 'Purnomo', 'Wardhana', 'Siregar', 'Nasution', 'Lubis', 'Harahap', 'Pasaribu',
    'Sinaga', 'Simanjuntak', 'Hutapea', 'Ginting', 'Tarigan', 'Sitorus', 'Tanjung', 'Chaniago', 'Piliang', 'Sikumbang',
    'Koto', 'Manurung', 'Sitompul', 'Simatupang', 'Nababan', 'Siahaan', 'Panjaitan', 'Hasibuan', 'Daulay', 'Batubara',
    'Subekti', 'Prasetyo', 'Hartono', 'Budiman', 'Hardiansyah', 'Widodo', 'Pangestu', 'Suharto', 'Yudhoyono', 'Baswedan',
    'Prabowo', 'Wahyudi', 'Firmansyah', 'Sulaeman', 'Ramadhan', 'Syahputra', 'Maulana', 'Firmanto', 'Hermawan', 'Irawan',
    'Suryono', 'Subagyo', 'Handoko', 'Adipati', 'Anggoro', 'Arifin', 'Atmowidjoyo', 'Bachtiar', 'Basuki', 'Cahyono', 'Damar',
    'Darsono', 'Hakim', 'Hamid', 'Haryanto', 'Hasanudin', 'Iskandar', 'Lazuardi', 'Lestari', 'Mahendra', 'Mangundiprojo',
    'Mardiono', 'Mulyadi', 'Pambudi', 'Pamungkas', 'Permadi', 'Prakoso', 'Prasetya', 'Prawiro', 'Purwanto', 'Putra',
    'Rahardjo', 'Rahman', 'Riyadi', 'Rusli', 'Sadikin', 'Sari', 'Sartono', 'Sasongko', 'Sudarmono', 'Sudirman',
    'Sujatmiko', 'Sukarno', 'Sulistyo', 'Sumantri', 'Nugraha', 'Wardana', 'Suherman', 'Kurnia', 'Pranoto', 'Handoko',
    'Sudrajat', 'Darmo', 'Kusworo', 'Abdullah', 'Abidin', 'Achmad', 'Adiansyah', 'Adiputra', 'Aditama', 'Aditya',
    'Afandi', 'Agustian', 'Agustina', 'Ahmad', 'Akbar', 'Alamsyah', 'Alfian', 'Ali', 'Alief', 'Amalia',
    'Amin', 'Amir', 'Anam', 'Ananda', 'Andika', 'Andini', 'Anggara', 'Anggraini', 'Ansori', 'Anto',
    'Anwar', 'Aprilia', 'Ardiansyah', 'Ardila', 'Ariyanto', 'Arman', 'Arsyad', 'Asari', 'Asmoro', 'Asri',
    'Astuti', 'Atmaja', 'Azhar', 'Azis', 'Aziz', 'Bachdim', 'Badri', 'Bahar', 'Baharudin', 'Bahri',
    'Bakar', 'Baskoro', 'Basri', 'Bawono', 'Cahyadi', 'Cahyani', 'Candrawinata', 'Christian', 'Christy', 'Damanik',
    'Damayanti', 'Daniswara', 'Darmawan', 'Daryanto', 'Fitriani'
]

LAST_NAMES_JAPANESE = [
    'Sato', 'Suzuki', 'Takahashi', 'Tanaka', 'Watanabe', 'Ito', 'Yamamoto', 'Nakamura', 'Kobayashi', 'Kato',
    'Yoshida', 'Yamada', 'Sasaki', 'Yamaguchi', 'Saito', 'Matsumoto', 'Inoue', 'Kimura', 'Hayashi', 'Shimizu',
    'Yamazaki', 'Mori', 'Abe', 'Ikeda', 'Hashimoto', 'Yamashita', 'Ishikawa', 'Nakajima', 'Maeda', 'Fujita',
    'Ogawa', 'Goto', 'Okada', 'Hasegawa', 'Murakami', 'Kondo', 'Ishii', 'Sakamoto', 'Endo', 'Aoki',
    'Fujii', 'Nishimura', 'Fukuda', 'Miura', 'Fujiwara', 'Okamoto', 'Matsuda', 'Nakagawa', 'Harada', 'Ono',
    'Tamura', 'Takeuchi', 'Kaneko', 'Wada', 'Nakano', 'Shibata', 'Ueda', 'Kojima', 'Miyazaki', 'Chiba',
    'Kudo', 'Kinoshita', 'Uchida', 'Murata', 'Matsui', 'Sugiyama', 'Kikuchi', 'Nomura', 'Sano', 'Otsuka',
    'Sugawara', 'Nishida', 'Arai', 'Ando', 'Sugimoto', 'Imai', 'Takagi', 'Miyake', 'Mochizuki', 'Nagai',
    'Noguchi', 'Okazaki', 'Sakai', 'Sekiguchi', 'Taniguchi', 'Ueno', 'Yabuki', 'Yokoyama', 'Yoshiba', 'Asai',
    'Baba', 'Date', 'Ebara', 'Fukushima', 'Hoshino', 'Fujimoto', 'Ishida', 'Iwasaki', 'Koyama', 'Maruyama',
    'Masuda', 'Ota', 'Nakayama', 'Morita', 'Aida', 'Aizawa', 'Akagi', 'Akashi', 'Akita', 'Akiyama', 'Asada',
    'Asano', 'Hada', 'Haga', 'Hamada', 'Hara', 'Hata', 'Hattori', 'Hayakawa', 'Higashi', 'Higa',
    'Hino', 'Hirano', 'Hirata', 'Hirose', 'Honda', 'Honma', 'Hori', 'Horii', 'Ibuki', 'Ichikawa',
    'Ida', 'Igarashi', 'Iida', 'Imamura', 'Inaba', 'Ishibashi', 'Ishihara', 'Ishimoto', 'Isobe', 'Itoh',
    'Iwai', 'Iwata', 'Izumi', 'Jin', 'Kagawa', 'Kai', 'Kaji', 'Kajihara', 'Kamada', 'Kamei',
    'Kameyama', 'Kamijo', 'Kamiya', 'Kanai', 'Kano', 'Kasai', 'Kase', 'Katayama', 'Katoh', 'Kawabata',
    'Kawaguchi', 'Kawahara', 'Morita'
]

LAST_NAMES_KOREAN = [
    'Kim', 'Lee', 'Park', 'Choi', 'Jung', 'Kang', 'Cho', 'Yoon', 'Jang', 'Lim',
    'Han', 'Oh', 'Seo', 'Shin', 'Kwon', 'Hwang', 'Ahn', 'Song', 'Ryu', 'Hong',
    'Ko', 'Moon', 'Yang', 'Son', 'Bae', 'Baek', 'Huh', 'Yoo', 'Nam', 'Sim',
    'Roh', 'Ha', 'Kwak', 'Sung', 'Cha', 'Joo', 'Woo', 'Koo', 'Im', 'Ra',
    'Min', 'Jin', 'Ji', 'Eom', 'Chae', 'Won', 'Chun', 'Bang', 'Kong', 'Hyun',
    'Ham', 'Byun', 'Yeom', 'Bok', 'Pyeon', 'Noh', 'Tak', 'Seok', 'Sun', 'Ok',
    'Mo', 'Ban', 'Kal', 'Pyo', 'Mae', 'Eum', 'Pil', 'Dan', 'Tan', 'Bong',
    'Gyeon', 'So', 'Seol', 'Ma', 'Sa', 'Guk', 'Sam', 'Doh', 'Hwangbo', 'Jegal',
    'Sagong', 'Seonwoo', 'Dokgo', 'Dongbang', 'Mangjeol', 'Chungho', 'Hyeop', 'No', 'Mok', 'Bing',
    'An', 'Chang', 'Cheon', 'Choe', 'Do', 'Dong', 'Doo', 'Hahm', 'Heo', 'Jeon',
    'Jeong', 'Jo', 'Ju', 'Jun', 'Ki', 'Kil', 'Koh', 'Ku', 'Maeng', 'Mun',
    'Myung', 'Na', 'Namgung', 'Pae', 'Paik', 'Rha', 'Rhee', 'Rim', 'Ro', 'Seong',
    'Shim', 'Sin', 'Sohn', 'Suk', 'Sunwoo', 'Um', 'Yeo', 'Chu', 'Dang', 'Wang',
    'Geum', 'Chung', 'Goo', 'Whang', 'You', 'Yun', 'Eun', 'Gang', 'Gim', 'Go', 'Gong',
    'Gu', 'O', 'Phang', 'Ri', 'Ryoo', 'Suh', 'Bu', 'Dam', 'Don', 'Eoh',
    'Gae', 'Gak', 'Gal', 'Gam', 'Gan', 'Geon', 'Gung', 'Gwak', 'Gwon', 'Hyung',
    'Ja', 'Jeom', 'Jong', 'Kook', 'Man', 'Mi', 'Muk', 'Nae', 'Nan', 'Noe',
    'On', 'Ong', 'Pan', 'Pang', 'Pung', 'Ran', 'Rang', 'Roe', 'Ryom', 'Sang',
    'Seon', 'Si', 'Sobong', 'Tae', 'Wee', 'Wi', 'Woon', 'Ye', 'Yeon', 'Yim',
    'Yu'
]

LAST_NAMES_RUSSIAN = [
    'Ivanov', 'Smirnov', 'Kuznetsov', 'Popov', 'Vasiliev', 'Petrov', 'Sokolov', 'Mikhailov', 'Novikov', 'Fedorov',
    'Morozov', 'Volkov', 'Alekseev', 'Lebedev', 'Semenov', 'Egorov', 'Pavlov', 'Kozlov', 'Stepanov', 'Nikolaev',
    'Orlov', 'Andreev', 'Makarov', 'Nikitin', 'Zakharov', 'Zaytsev', 'Soloviev', 'Borisov', 'Yakovlev', 'Vorobiev',
    'Karpov', 'Sergeev', 'Frolov', 'Aleksandrov', 'Dmitriev', 'Korolev', 'Gusev', 'Shcherbakov', 'Tikhonov', 'Kuzmin',
    'Belyaev', 'Tarasov', 'Belov', 'Komarov', 'Medvedev', 'Antonov', 'Ilyin', 'Krasnov', 'Sorokin', 'Bogdanov',
    'Vinogradov', 'Voronov', 'Gerasimov', 'Davidov', 'Ermakov', 'Zhukov', 'Zhuravlev', 'Ignatov', 'Kazakov', 'Lapin',
    'Mironov', 'Nazarenko', 'Ovchinnikov', 'Pankratov', 'Rozhkov', 'Savitskiy', 'Trofimov', 'Ushakov', 'Fedoseev', 'Kharlamov',
    'Chernov', 'Shubin', 'Yudin', 'Baranov', 'Vlasov', 'Golubev', 'Demyanov', 'Efimov', 'Zotov', 'Isaev', 'Abramov',
    'Afanasyev', 'Danilov', 'Dementiev', 'Drozdov', 'Fedotov', 'Filipov', 'Gavrilyuk', 'Gorbachev', 'Gorkiy', 'Gorshkov',
    'Grigoriev', 'Gromov', 'Kalin', 'Kalinin', 'Kazan', 'Kiselev', 'Klimov', 'Kolesnikov', 'Konovalov', 'Koshelev',
    'Kovalev', 'Kravtsov', 'Krylov', 'Kudryavtsev', 'Kulik', 'Leonov', 'Levin', 'Loginov', 'Maksimov', 'Malyshev',
    'Markov', 'Maslov', 'Matveev', 'Kiselyov', 'Titov', 'Kulikov', 'Romanov', 'Korolyov', 'Ponomaryov', 'Grigoryev',
    'Lazarev', 'Ershov', 'Sobolev', 'Ryabov', 'Polyakov', 'Tsvetkov', 'Abakumov', 'Abalikhin', 'Abaturov', 'Abramov',
    'Abrosimov', 'Avdeyev', 'Averin', 'Averyanov', 'Avilov', 'Avtomonov', 'Agapov', 'Agafonov', 'Ageyev', 'Agrenev',
    'Akulov', 'Akulshin', 'Alekhin', 'Alekseyev', 'Aleshin', 'Almazov', 'Alyokhin', 'Alyoshin', 'Amvrosimov', 'Ananyev',
    'Anashkin', 'Andreyev', 'Andriyanov', 'Andronov', 'Andropov', 'Anisimov', 'Anikin', 'Ankudinovich', 'Antipin', 'Antipov',
    'Antokhin', 'Apollonov', 'Apushkin', 'Arakcheyev', 'Arbuzov', 'Arefyev', 'Aristarkhov', 'Aristov', 'Arsenyev', 'Artamonov',
    'Artemyev', 'Artyomov', 'Arkhangelskii', 'Arkhipov', 'Asafyev', 'Aseev', 'Astakhov', 'Astafyev', 'Afonin', 'Akhmatov',
    'Babikov', 'Babin', 'Babkin', 'Baburin', 'Bagrov', 'Bazhanov', 'Bazhenov', 'Bazanov', 'Bazarov', 'Baykov',
    'Baklanov', 'Balabanov', 'Balakin', 'Balakirev', 'Balandin', 'Balashov', 'Balmont', 'Balsunovskiy', 'Bannikov', 'Baranovskiy',
    'Baratynskiy'
]

LAST_NAMES_THAI = [
    'Prasert', 'Suksom', 'Saetang', 'Wongsuwan', 'Saelim', 'Thongdee', 'Chaiprasert', 'Rattanakul', 'Wattanapanit', 'Kittikachorn',
    'Boonserm', 'Pholsena', 'Sirisena', 'Chaiyaphum', 'Suwannarat', 'Kaewmanee', 'Saelao', 'Saehan', 'Saelee', 'Saengkaew',
    'Petchpradub', 'Ratanaporn', 'Sombatdee', 'Thongchai', 'Bunyarat', 'Chanthara', 'Dechawat', 'Eamsombat', 'Janthong', 'Klinsukhon',
    'Liangpibul', 'Meesuk', 'Namwong', 'Onkaew', 'Phonpradit', 'Raksasri', 'Sangthong', 'Tangcharoen', 'Udomsuk', 'Vongpanich',
    'Wongprasert', 'Yindee', 'Anurak', 'Boonmee', 'Charoensuk', 'Damrongkiat', 'Hengcharoen', 'Intarat', 'Jaroenrat', 'Khamdee',
    'Lertvilai', 'Manirat', 'Nopparat', 'Panich', 'Ruengkit', 'Srisawat', 'Tantivejkul', 'Vechasit', 'Wattanasin', 'Yongpradit',
    'Bunlue', 'Chansiri', 'Decharat', 'Ekkachai', 'Jiamsiri', 'Kiatwong', 'Leelawat', 'Meechai', 'Niyom', 'Phromsri',
    'Rungruang', 'Supamitr', 'Thepprasit', 'Vorakit', 'Wiriyakul', 'Amornrat', 'Boonchuay', 'Chaichana', 'Direkwat', 'Eampradit',
    'Jirawattana', 'Komonwan', 'Lertpong', 'Mahatthanakul', 'Namchai', 'Ongwit', 'Phinit', 'Rattanamanee', 'Saksit', 'Suwannee',
    'Tanaporn', 'Uthairat', 'Vorachit', 'Wiparat', 'Yossakul', 'Adisorn', 'Boonyarat', 'Chaisiri', 'Duangchan', 'Isarasena',
    'Janpen', 'Kongsomboon', 'Likhit', 'Mongkolrat', 'Nimitkul', 'Pakdeewong', 'Piyawat', 'Rapeepong', 'Siriphat', 'Teerasilp',
    'Akaraseth', 'Amornvivat', 'Anantachai', 'Apisith', 'Boonlerd', 'Boontham', 'Chaianan', 'Chaikul', 'Chaimongkol', 'Chaisuk',
    'Chanchai', 'Charoenphon', 'Chavalit', 'Chiamprasert', 'Chotikavanich', 'Damrongsak', 'Darathai', 'Dechapanya', 'Ditsakul', 'Eakkachai',
    'Intarathai', 'Jampathong', 'Jangprasert', 'Jiraporn', 'Kaewkam', 'Kanthasit', 'Karnchanarat', 'Kasemsuk', 'Kiatphong', 'Kittipong',
    'Klinhom', 'Kongkiat', 'Kraisri', 'Kulwong', 'Lertchai', 'Mahidol', 'Maneewan', 'Meethong', 'Mongkolsuk', 'Naowarat',
    'Nilphan', 'Nitiwong', 'Pakdeechit', 'Panichkul', 'Payakkarat', 'Phanit', 'Phromphan', 'Phuengsuk', 'Pimpasorn', 'Piyawong',
    'Pongpanit', 'Pornprapha', 'Prasertsuk', 'Preechakul', 'Raksakul', 'Ratanakorn', 'Ruangchai', 'Ruangdet', 'Saengchan', 'Saksiri',
    'Samakkhi', 'Santipab', 'Sarathorn', 'Sirichana', 'Somwang', 'Songkran', 'Sukchai', 'Supharat', 'Suriyawong', 'Tanawat',
    'Teerakorn', 'Thammavong', 'Ratanakul', 'Chatchavalpong', 'Thanasuk', 'Panyarachun', 'Boonyaratglin', 'Charoenrat', 'Sawatdee', 'Rattanakosin',
    'Chaiyasit', 'Damrong', 'Jaturapat', 'Kanchanaburi', 'Lertrat', 'Manakul', 'Na Nakorn', 'Ounruan', 'Pattanakul', 'Ruangrit',
    'Sombat', 'Tantiprasert', 'Vongpanit', 'Wongrat', 'Yothaprasert', 'Boonperm', 'Eamprasert', 'Jaroenruk', 'Luangphat', 'Narat',
    'Ongsakul', 'Pholprasert', 'Ratanawong', 'Somchai', 'Teerasuk', 'Upatham', 'Varasuk', 'Wattanasuk', 'Yimprasert', 'Anantakul',
    'Boonsri', 'Chaovalit', 'Dumrong', 'Ekaphan', 'Indrasena', 'Jirawat', 'Kittisuk', 'Lertprasert', 'Maneewong', 'Onnom',
    'Phonrat', 'Songkram', 'Theerapat', 'Uthaisuk', 'Visut', 'Wichit', 'Yodrak', 'Apichat', 'Boontam', 'Charan',
    'Duangrat', 'Ekarat', 'Issarasena', 'Juntarat', 'Kulrat', 'Limprasert', 'Nualrat', 'Osathanugrah', 'Phromsuk', 'Ratanarat',
    'Srisuk', 'Udomrat', 'Vongprasert', 'Yooktasevi', 'Arayasook', 'Bencharong', 'Boonruang', 'Chaiwong', 'Jitpakdee', 'Karnchanachote',
    'Kasemsri', 'Kiatvong', 'Kongsuk', 'Kulwanich', 'Lertwong', 'Na Ayudhya', 'Navakul', 'Phakdeesuk', 'Phanuwat', 'Pongpanich',
    'Praditsuk', 'Pramoj', 'Puranananda', 'Rojanapruk', 'Sanprasert', 'Sathitvong', 'Sena', 'Sriboon', 'Suwanarat', 'Adulyadej', 'Amatayakul',
    'Amratisha', 'Anuman', 'Apichatpong', 'Arayaskul', 'Ariyawong', 'Asavahame', 'Assavanig', 'Boonnak', 'Boonprasert', 'Bunyaratglin',
    'Chaemchoi', 'Chaiyaporn', 'Chaloemtiarana', 'Chantarasombat', 'Charoenkrung', 'Charoenpokphand', 'Chearavanont', 'Chiamsiri', 'Chirathivat', 'Chokevivat',
    'Chomanan', 'Chuaphan', 'Chulamorkot', 'Intarakumnerd', 'Israngkun', 'Jantarat', 'Jarupat', 'Jenwitheesuk', 'Jintanakan', 'Jitphong',
    'Jitsupap', 'Jittasiri', 'Kaewprasert', 'Kamhang', 'Kanjanapas', 'Kasetsart', 'Kittisakkul', 'Kongkanand', 'Krairiksh', 'Kriangsak',
    'Krittiyanunt', 'Kularb', 'Kunjara', 'Lamsam', 'Luang', 'Maneerat', 'Na-Chiangmai', 'Na-Lampang', 'Na-Ranong', 'Na-Songkhla',
    'Nakornthap', 'Narksuk', 'Nimmanahaeminda', 'Nivatvongs', 'Noppakhun', 'Paiboon', 'Pakdeeviroch', 'Panupong', 'Patanapong', 'Phasuk',
    'Phichai', 'Phitsanulok', 'Phongsathorn', 'Phrapradaeng', 'Pichit', 'Ratanatray', 'Phonphimon', 'Saewong', 'Boonma', 'Chantarat',
    'Kongkaew', 'Lekrat', 'Nakarat', 'Phetcharat', 'Thongkam', 'Wichaidit', 'Yodmanee', 'Bunnak', 'Charnvit', 'Duangmanee'
]

LAST_NAMES_WESTERN = [
    'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
    'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin',
    'Lee', 'Perez', 'Thompson', 'White', 'Harris', 'Sanchez', 'Clark', 'Ramirez', 'Lewis', 'Robinson',
    'Walker', 'Young', 'Allen', 'King', 'Wright', 'Scott', 'Torres', 'Nguyen', 'Hill', 'Flores',
    'Green', 'Adams', 'Nelson', 'Baker', 'Hall', 'Rivera', 'Campbell', 'Mitchell', 'Carter', 'Roberts',
    'Gomez', 'Phillips', 'Evans', 'Turner', 'Diaz', 'Parker', 'Cruz', 'Edwards', 'Collins', 'Reyes',
    'Stewart', 'Morris', 'Morales', 'Murphy', 'Cook', 'Rogers', 'Gutierrez', 'Ortiz', 'Morgan', 'Cooper',
    'Peterson', 'Bailey', 'Reed', 'Kelly', 'Howard', 'Ramos', 'Kim', 'Cox', 'Ward', 'Richardson',
    'Watson', 'Brooks', 'Chavez', 'Wood', 'James', 'Bennett', 'Gray', 'Mendoza', 'Ruiz', 'Hughes',
    'Price', 'Alvarez', 'Castillo', 'Sanders', 'Patel', 'Myers', 'Long', 'Ross', 'Foster', 'Jimenez',
    'Powell', 'Jenkins', 'Perry', 'Russell', 'Sullivan', 'Bell', 'Coleman', 'Butler', 'Henderson', 'Barnes',
    'Fisher', 'Vasquez', 'Simmons', 'Romero', 'Jordan', 'Patterson', 'Alexander', 'Hamilton', 'Graham', 'Reynolds',
    'Griffin', 'Wallace', 'Moreno', 'West', 'Cole', 'Hayes', 'Bryant', 'Herrera', 'Gibson', 'Ellis',
    'Harrison', 'McDonald', 'Marshall', 'Murray', 'Freeman', 'Wells', 'Webb', 'Simpson', 'Stevens', 'Tucker',
    'Porter', 'Hunter', 'Hicks', 'Crawford', 'Henry', 'Boyd', 'Mason', 'Kennedy', 'Warren', 'Dixon',
    'Burns', 'Gordon', 'Shaw', 'Holmes', 'Rice', 'Robertson', 'Hunt', 'Black', 'Daniels', 'Palmer',
    'Mills', 'Nichols', 'Grant', 'Knight', 'Ferguson', 'Rose', 'Stone', 'Hawkins', 'Dunn', 'Perkins',
    'Hudson', 'Spencer', 'Gardner', 'Stephens', 'Payne', 'Pierce', 'Berry', 'Matthews', 'Arnold', 'Wagner',
    'Willis', 'Ray', 'Watkins', 'Olson', 'Carroll', 'Duncan', 'Snyder', 'Hart', 'Cunningham', 'Bradley',
    'Lane', 'Andrews', 'Gonzales', 'Abbott', 'Abernathy', 'Abney', 'Acosta', 'Adair', 'Adkins', 'Agnew',
    'Aiken', 'Akers', 'Albertson', 'Albrecht', 'Alcorn', 'Alden', 'Alderman', 'Aldrich', 'Aldridge', 'Alford',
    'Allard', 'Alley', 'Allison', 'Allred', 'Almond', 'Alston', 'Altman', 'Alvord', 'Amador', 'Amato',
    'Ambrose', 'Ames', 'Amick', 'Ammon', 'Amos', 'Anagnostou', 'Anders', 'Andersen', 'Andrade', 'Angel',
    'Anglin', 'Anthony', 'Apple', 'Applegate', 'Appleton', 'Archer', 'Archibald', 'Archuleta', 'Ard', 'Ardoin',
    'Arellano', 'Arend', 'Arends', 'Argent', 'Argo', 'Argyle', 'Arias', 'Armas', 'Armbruster', 'Armenta',
    'Armitage', 'Armor', 'Armour', 'Armstrong', 'Arnason', 'Arndt', 'Arneson', 'Arnett', 'Harper', 'Fox',
    'Riley', 'Carpenter', 'Weaver', 'Greene', 'Lawrence', 'Elliott', 'Sims', 'Austin', 'Peters', 'Kelley',
    'Franklin', 'Lawson', 'Fields', 'Ryan', 'Schmidt', 'Carr', 'Wheeler', 'Chapman', 'Oliver', 'Montgomery',
    'Richards', 'Williamson', 'Johnston', 'Banks', 'Meyer', 'Bishop', 'McCoy', 'Howell', 'Morrison', 'Hansen',
    'Fernandez', 'Garza', 'Harvey', 'Little', 'Burton', 'Stanley', 'George', 'Jacobs', 'Reid', 'Fuller',
    'Lynch', 'Dean', 'Gilbert', 'Garrett', 'Welch', 'Larson', 'Owen', 'Castaneda', 'Barker', 'Burke',
    'Guzman', 'Page', 'Munoz', 'Ball', 'Keller', 'Chandler', 'Weber', 'Leonard', 'Walsh', 'Lyons',
    'Ramsey', 'Wolfe', 'Schneider', 'Mullins', 'Benson', 'Sharp', 'Bowen', 'Daniel', 'Barber', 'Cummings',
    'Hines', 'Baldwin', 'Griffith', 'Valdez', 'Hubbard', 'Salazar', 'Reeves', 'Warner', 'Lucas', 'Cross',
    'Stevenson', 'Mann', 'Maldonado', 'Fleming', 'Bowers', 'Holloway', 'Drake', 'Robbins', 'Curtis', 'Newton',
    'Pena', 'Conway', 'Buchanan', 'Norris', 'Copeland', 'Harlan', 'Glover', 'Hickman', 'Harding', 'Pratt',
    'Padilla', 'Burgess', 'Kemp', 'Love', 'Rhodes', 'Bridges', 'Hardy', 'Schultz', 'Swift', 'Ingram',
    'Terry', 'Vargas', 'Barton', 'Schroeder', 'Burch', 'Goodwin', 'Doyle', 'Moon', 'Nixon', 'Marsh',
    'Shannon', 'Vance', 'Giles', 'Cain', 'Short', 'Gentry', 'Mckinney', 'Holt', 'Patton', 'Potter',
    'Wise', 'Shepherd', 'Strickland', 'Blair', 'Humphrey', 'Sloan', 'Roberson', 'Kirby', 'Rowe', 'Preston',
    'Hodge', 'Finley', 'Sheppard', 'Savage', 'Hester', 'Solomon', 'Hess', 'Browning', 'Bates', 'Mckenzie',
    'Brock', 'Mccarthy', 'Ammons', 'Archie', 'Arrington', 'Ash', 'Ashby', 'Ashley', 'Ashton', 'Atkins',
    'Atkinson', 'Atwater', 'Avery', 'Ayala', 'Ayers', 'Babb', 'Babcock', 'Bacon', 'Bagley', 'Baird',
    'Ballard', 'Barclay', 'Barden', 'Barfield', 'Barkley', 'Barlow', 'Barnard', 'Barnett', 'Barney', 'Barnhart',
    'Barr', 'Barrett', 'Barron', 'Barrow', 'Barry', 'Bartlett', 'Bass', 'Bassett', 'Bateman', 'Battle',
    'Bauer', 'Baughman', 'Baxter', 'Beach', 'Beal', 'Beam', 'Bean', 'Beard', 'Beasley', 'Beck',
    'Becker', 'Beckett', 'Beckham', 'Beckman', 'Beckwith', 'Beech', 'Beeler', 'Bellamy', 'Belmont', 'Bender',
    'Benedict', 'Benitez', 'Benjamin', 'Bentley', 'Benton', 'Berg', 'Berger', 'Bergman', 'Bernard', 'Bertram',
    'Best', 'Betts', 'Bevan', 'Beverly', 'Beyer', 'Biddle', 'Biggs', 'Billings', 'Bingham', 'Birch',
    'Bird', 'Blackburn', 'Blackwell', 'Blake', 'Blakely', 'Blalock', 'Blanchard', 'Blankenship', 'Blanton', 'Blevins',
    'Bliss', 'Bloom', 'Blount', 'Blue', 'Blunt', 'Blythe', 'Boatwright', 'Bobbitt', 'Boggs', 'Boles',
    'Bolton', 'Bond', 'Bonds', 'Bonham', 'Bonner', 'Booker', 'Boone', 'Booth', 'Borden', 'Boseman',
    'Boston', 'Boswell', 'Boucher', 'Boudreaux', 'Bourne', 'Bowles', 'Bowman', 'Boyce', 'Boyer', 'Boyle',
    'Boynton', 'Bozeman', 'Bracken', 'Bradbury', 'Bradford', 'Bradshaw', 'Brady', 'Bragg', 'Bramlett', 'Branch',
    'Brand', 'Brandon', 'Brandt', 'Branham', 'Brannon', 'Brantley', 'Braswell', 'Bratton', 'Braun', 'Braxton',
    'Bray', 'Breeden', 'Brennan', 'Brewer', 'Brewster', 'Briggs', 'Bright', 'Brinkley', 'Britt', 'Britton',
    'Bronson', 'Brooke', 'Broom', 'Brothers', 'Brower', 'Browne', 'Bruce', 'Brumfield', 'Bryan', 'Buck',
    'Buckley', 'Buckner', 'Bullock', 'Bunch', 'Bundy', 'Bunker', 'Burden', 'Burdette', 'Burdick', 'Burkett',
    'Burks', 'Burnett', 'Burnham', 'Burr', 'Burris', 'Burroughs', 'Burrow', 'Burt', 'Busby', 'Bush',
    'Butterworth', 'Button', 'Butts', 'Byers', 'Bynum', 'Byrd', 'Byrne', 'Cable', 'Cagle', 'Calderon',
    'Caldwell', 'Calhoun', 'Calkins', 'Callahan', 'Callaway', 'Calloway', 'Calvert', 'Cameron', 'Camp', 'Canada',
    'Canady', 'Cannon', 'Cantrell', 'Cantu', 'Capps', 'Carey', 'Carlin', 'Carlisle', 'Carlson', 'Carlton',
    'Carmack', 'Carmichael', 'Carnahan', 'Carnes', 'Carney', 'Carrick', 'Carrier', 'Carrillo', 'Carrington', 'Carson',
    'Cartwright', 'Carver', 'Casey', 'Cash', 'Caskey', 'Cassidy', 'Castle', 'Castro', 'Cates', 'Cathey',
    'Cato', 'Caudill', 'Caulfield', 'Cavanaugh', 'Cave', 'Cawood', 'Cearley', 'Cecil', 'Chadwick', 'Chaffin',
    'Chamberlain', 'Chambers', 'Champion', 'Chance', 'Chaney', 'Chappell', 'Charles', 'Chase', 'Chastain', 'Chatham',
    'Chau', 'Cheek', 'Cheney', 'Chenault', 'Cherry', 'Cheshire', 'Chesney', 'Chester', 'Childers', 'Childress',
    'Childs', 'Chilton', 'Chisholm', 'Choate', 'Christian', 'Christie', 'Christopher', 'Church', 'Churchill', 'Clanton',
    'Clapp', 'Clarke', 'Clarkson', 'Clay', 'Clayton', 'Cleary', 'Clegg', 'Clem', 'Clemens', 'Clements',
    'Clemons', 'Cleveland', 'Clevenger', 'Click', 'Clifford', 'Clifton', 'Cline', 'Clinton', 'Close', 'Cloud',
    'Clough', 'Clower', 'Coats', 'Cobb', 'Coble', 'Cochran', 'Cochrane', 'Cockrell', 'Cody', 'Coe',
    'Coffey', 'Coffin', 'Coffman', 'Cogan', 'Cogburn', 'Cogdill', 'Cohen', 'Coker', 'Colbert', 'Colburn',
    'Colby', 'Coles', 'Colley', 'Collier', 'Collum', 'Colman', 'Colon', 'Colvin', 'Colwell', 'Combs',
    'Comer', 'Compton', 'Conant', 'Condit', 'Condon', 'Cone', 'Congdon', 'Conger', 'Conklin', 'Conley',
    'Conn', 'Connell', 'Connelly', 'Conner', 'Connolly', 'Connor', 'Conrad', 'Conroy', 'Cooke', 'Cooksey',
    'Cooley', 'Coolidge', 'Coombs', 'Coon', 'Coonce', 'Coons', 'Cope', 'Copley', 'Copp', 'Coppage',
    'Corbett', 'Corbin', 'Corcoran', 'Cordell', 'Corder', 'Corey', 'Cormier', 'Cornelius', 'Cornell', 'Cornish',
    'Cornwall', 'Corrigan', 'Corso', 'Cortez', 'Cosby', 'Costello', 'Cothran', 'Cotter', 'Cottle', 'Cotton',
    'Cottrell', 'Couch', 'Coughlin', 'Coulter', 'Council', 'Countryman', 'Courson', 'Courtney', 'Cousins', 'Coutu',
    'Couture', 'Covert', 'Covington', 'Cowan', 'Cowart', 'Cowell', 'Cowles', 'Crabtree', 'Craddock', 'Craft',
    'Craig', 'Crain', 'Cramer', 'Crane', 'Cranford', 'Cranmer', 'Craven', 'Crawley', 'Crayton', 'Creel',
    'Crenshaw', 'Crespo', 'Crews', 'Crider', 'Crisp', 'Crist', 'Crocker', 'Crockett', 'Croft', 'Croll',
    'Cromer', 'Cromwell', 'Cronin', 'Crook', 'Crosby', 'Crossman', 'Crouch', 'Crouse', 'Crow', 'Crowder',
    'Crowe', 'Crowell', 'Crowley', 'Crum', 'Crump', 'Cruse', 'Culbertson', 'Cullen', 'Culp', 'Culver',
    'Cummins', 'Curley', 'Curran', 'Currie', 'Curry', 'Curtin', 'Cushing', 'Cushman', 'Cutrer', 'Cutter',
    'Davies', 'Griffiths', 'Rees', 'Lloyd', 'Vaughan', 'Hopkins', 'Howells', 'Pritchard', 'Llewellyn', 'Harries',
    'Paterson', 'MacKenzie', 'MacLeod', 'MacDonald', 'Fraser', 'McIntosh', 'Thomson', 'Sinclair', 'Davidson', 'Sutherland',
    'Kerr', 'MacKay', 'Munro', 'Ritchie', 'Urquhart', 'OBrien', 'OConnor', 'ONeill', 'OReilly', 'OSullivan',
    'Gallagher', 'ODonnell', 'Farrell', 'Fitzgerald', 'Higgins', 'Daly', 'Flynn', 'Donnelly', 'Kavanagh', 'Nolan',
    'Callaghan', 'Fitzpatrick', 'Quinn', 'Sheehan', 'Whelan',
]

TEN_NAM_VIET = [
    'Huy', 'Nam', 'Phong', 'Dũng', 'Khánh', 'Việt', 'Anh', 'Long', 'Đạt', 'Sơn',
    'Tùng', 'Bảo', 'Phát', 'Thịnh', 'Khoa', 'Hiếu', 'Cường', 'Tài', 'Vinh', 'Quân',
    'Kiên', 'Hùng', 'Thắng', 'Hoàng', 'Tân', 'Nhật', 'Triết', 'Hưng', 'Nghĩa', 'Nhân',
    'Khang', 'Lâm', 'Vũ', 'Bình', 'Trí', 'Phước', 'Tuấn', 'Đức', 'Hải', 'Hiệp',
    'Châu', 'Luân', 'Trung', 'Nhiên', 'Chương', 'Bách', 'Hào', 'Viễn', 'Thành', 'Danh',
    'Lộc', 'Khôi', 'Nguyên', 'Thuận', 'Duy', 'Sang', 'Kiệt', 'Lập', 'Phú', 'Tiến',
    'An', 'Dương', 'Khiêm', 'Trọng', 'Định', 'Toàn', 'Quyết', 'Cương', 'Huân', 'Quang',
    'Đăng', 'Văn', 'Tấn', 'Thái', 'Lân', 'Khoát', 'Tường', 'Cảnh', 'Thiện', 'Trường',
    'Tuệ', 'Hiển', 'Vỹ', 'Phi', 'Đông', 'Hậu', 'Sáng', 'Chiêu', 'Giác', 'Khởi',
    'Cát', 'Hoan', 'Ninh', 'Thao', 'Tiệp', 'Uy', 'Vĩnh', 'Thạc', 'Điền', 'Cẩm',
    'Doanh', 'Du', 'Giáp', 'Hân', 'Kỷ', 'Mẫn', 'Nghị', 'Nhất', 'Nhựt', 'Minh',
    'Phúc', 'Công', 'Chí', 'Giang', 'Xuân', 'Ân', 'Ba', 'Bắc', 'Chính', 'Chung',
    'Đan', 'Điệp', 'Đoan', 'Đồng', 'Gia', 'Hiền', 'Hòa', 'Hoàn', 'Hợi', 'Huấn',
    'Kha', 'Khương', 'Kỳ', 'Luật', 'Lực', 'Lương', 'Mạnh', 'Ngọc', 'Quốc', 'Quy',
    'Quyền', 'Tâm', 'Thạch', 'Thạch', 'Thăng', 'Thanh', 'Trực', 'Ân', 'Đình', 'Hoài',
    'Hồng', 'Hữu', 'Khai'
]

TEN_NU_VIET = [
    'Trang', 'Linh', 'Hương', 'Lan', 'Huyền', 'Nhi', 'Vy', 'Thảo', 'Hà', 'Trâm',
    'Ngân', 'Hoa', 'Tuyết', 'Mai', 'Quỳnh', 'Anh', 'Dung', 'Oanh', 'Diệp', 'Chi',
    'Hằng', 'Thư', 'Nguyệt', 'Vân', 'My', 'Quyên', 'Thủy', 'Yến', 'Ngọc', 'Nga',
    'Tú', 'Giang', 'Ly', 'Châu', 'Uyên', 'Hân', 'Hiền', 'Loan', 'Thơ', 'Hạnh',
    'Phương', 'Bình', 'Nhung', 'Đoan', 'Tâm', 'Sen', 'Đào', 'Mơ', 'Trúc', 'Bội',
    'Mi', 'Xuyến', 'Duyên', 'Khuê', 'Cúc', 'Phượng', 'Nương', 'Lệ', 'Trà', 'Hạ',
    'Ánh', 'Thùy', 'Băng', 'Cát', 'Thục', 'Hoài', 'Nhã', 'An', 'Thúy', 'Kiều',
    'Diệu', 'Thi', 'Mộng', 'Tường', 'Khả', 'Lam', 'Liễu', 'Huệ', 'San', 'Sương',
    'Tố', 'Trân', 'Ý', 'Đan', 'Dạ', 'Hảo', 'Hường', 'Nghi', 'Quế', 'Vàng',
    'Xoan', 'Yên', 'Mộc', 'Mây', 'Nắng', 'Điệp', 'Giao', 'Hạc', 'Huyên', 'Kha',
    'Khuyên', 'Lài', 'Lành', 'Lộc', 'Lụa', 'Mến', 'Miên', 'Mẫn', 'Na', 'Ngà',
    'Nhu', 'Nụ', 'Phấn', 'Sa', 'Sam', 'Sim', 'Sâm', 'Tần', 'Thơm', 'Tiên',
    'Liên', 'Trinh', 'Như', 'Thy', 'Bích', 'Hồng', 'Khánh', 'Thanh', 'Thu', 'Bảo', 'Cam',
    'Cẩm', 'Châm', 'Dao', 'Diễm', 'Hải', 'Hậu', 'Hiệp', 'Hiếu', 'Hoàng', 'Kim',
    'Minh', 'Mùi', 'Mỹ', 'Nữ', 'Phi', 'Phúc', 'Thoa', 'Thuần', 'Thuận', 'Thụy',
    'Thương', 'Thường', 'Bảo', 'Cầm', 'Lê'
]


# ==============================================================================
# BO SUNG DU LIEU MO RONG CHO CAC QUOC GIA (INDIAN, THAI, CHINESE, KOREAN, ETC.)
# ==============================================================================

_EXTRA_MALE_INDIAN = [
    "Aarav", "Vihaan", "Aditya", "Reyansh", "Arjun", "Sai", "Arnav", "Aayush", "Krishna", "Ishaan",
    "Shaurya", "Atharv", "Advik", "Pranav", "Advaith", "Aaryan", "Dhruv", "Kabir", "Rudra", "Rishi",
    "Darsh", "Shivansh", "Aniket", "Tanmay", "Kartik", "Yash", "Harsh", "Devansh", "Samarth", "Parth",
    "Madhav", "Kunal", "Raghav", "Manish", "Gaurav", "Siddharth", "Nikhil", "Abhinav", "Sameer", "Vikram",
    "Mohit", "Karan", "Chirag", "Akash", "Varun", "Mayank", "Rohit", "Suresh", "Ramesh", "Dinesh",
    "Mukesh", "Rajesh", "Naresh", "Sunil", "Anil", "Pawan", "Manoj", "Pankaj", "Vipin", "Alok",
    "Ajay", "Vijay", "Deepak", "Sandeep", "Pradeep", "Kuldeep", "Harish", "Girish", "Satish", "Umesh",
    "Kamal", "Bipin", "Tarun", "Naveen", "Praveen", "Sachin", "Amit", "Sumit", "Vineet", "Puneet"
]

_EXTRA_FEMALE_INDIAN = [
    "Aadya", "Diya", "Saanvi", "Ananya", "Aadhya", "Pari", "Kiara", "Myra", "Riya", "Anvi",
    "Ira", "Aarohi", "Prisha", "Anaya", "Sara", "Avani", "Aditi", "Navya", "Khushi", "Shruti",
    "Sneha", "Pooja", "Neha", "Kavya", "Simran", "Swati", "Megha", "Divya", "Shreya", "Roshni",
    "Sunita", "Geeta", "Seema", "Anita", "Suman", "Kiran", "Reena", "Meena", "Sangeeta", "Kavita",
    "Savita", "Bhavna", "Rashmi", "Pallavi", "Preeti", "Shikha", "Garima", "Monika", "Ritu", "Shilpa",
    "Deepa", "Mamta", "Nisha", "Vandana", "Archana", "Sushma", "Asha", "Usha", "Rekha", "Madhu",
    "Manju", "Sarita", "Alka", "Anju", "Bimla", "Champa", "Devi", "Ganga", "Gita", "Indu"
]

_EXTRA_LAST_INDIAN = [
    "Sharma", "Verma", "Gupta", "Mehta", "Jain", "Agarwal", "Shah", "Patel", "Singh", "Kumar",
    "Choudhary", "Mishra", "Pandey", "Tiwari", "Dubey", "Shukla", "Tripathi", "Yadav", "Rao", "Reddy",
    "Nair", "Pillai", "Menon", "Iyer", "Iyengar", "Bose", "Das", "Ghosh", "Banerjee", "Chatterjee",
    "Mukherjee", "Sengupta", "Dutta", "Roy", "Chakraborty", "Bhattacharya", "Chowdhury", "Basu", "Saha", "Nath",
    "Kundu", "Sarkar", "Mitra", "Biswas", "Mondal", "Paul", "Bhowmik", "Dey", "Pal", "Barman",
    "Majumdar", "Kaur", "Bhatia", "Malhotra", "Chopra", "Kapoor", "Khanna", "Arora", "Bhasin", "Sethi"
]

_EXTRA_MALE_THAI = [
    "Somchai", "Sombat", "Somkiat", "Somdej", "Somphong", "Somboon", "Sompot", "Prasert", "Preecha", "Pravit",
    "Prayut", "Prasit", "Prasan", "Pramote", "Prachya", "Nattawut", "Nattapong", "Nattapol", "Nattawat", "Natthakit",
    "Thanawat", "Thanaphat", "Thanapon", "Thanakorn", "Thanatorn", "Chatchai", "Chatree", "Chaturong", "Chaiwat", "Chainarong",
    "Kittisak", "Kittipong", "Kittichai", "Kitsada", "Kritsada", "Anan", "Anurat", "Anurak", "Adisak", "Apinan",
    "Boonchu", "Boonlert", "Boonmee", "Boonrod", "Boonterm", "Chalerm", "Chalermchai", "Chalermpol", "Charoen", "Charun",
    "Damrong", "Denchai", "Direk", "Dusit", "Ekkachai", "Ekkarat", "Itthiphon", "Jaran", "Jirawat", "Jirayu"
]

_EXTRA_FEMALE_THAI = [
    "Kanya", "Kanokwan", "Kamolwan", "Kulap", "Kanjana", "Kessara", "Ketkanok", "Malai", "Malee", "Mananya",
    "Mayuree", "Mali", "Nalinee", "Narumon", "Natnicha", "Nattaya", "Nipaporn", "Nopphawan", "Onanong", "Pakaporn",
    "Panadda", "Parichat", "Patcharee", "Pattama", "Pawinee", "Phailin", "Phonthip", "Pimchanok", "Pimpaka", "Ploy",
    "Porntip", "Pranee", "Prapaporn", "Prasarn", "Premwadee", "Ratana", "Ratchanee", "Rattanaporn", "Rattikarn", "Rewadee",
    "Rungrat", "Rungruedee", "Saengdao", "Saifon", "Samorn", "Sanitwong", "Sasithorn", "Siriporn", "Sirirat", "Siriyakorn"
]

_EXTRA_LAST_THAI = [
    "Suksom", "Wongsuwan", "Saetang", "Rattanakorn", "Chanthara", "Thepprasit", "Suwannarat", "Boonmee", "Charoensuk", "Saelim",
    "Saelee", "Saewong", "Saeheng", "Saetia", "Kaewmanee", "Petchpradab", "Thongkham", "Ruangdet", "Siriprasert", "Kittisuk",
    "Chaiyasit", "Phonprasert", "Chaisuk", "Khamdee", "Suksabai", "Panyasit", "Phrommanee", "Siriwong", "Rattanamanee", "Chantharat",
    "Wichitsuk", "Mongkolchai", "Thongdee", "Boonkerd", "Rattanasiri", "Kongkaew", "Somnuek", "Sombat", "Pattanasuk", "Ruenrom",
    "Shinawatra", "Vejjajiva", "Silpa-archa", "Chirathivat", "Chearavanont", "Yoovidhya", "Sirivadhanabhakdi", "Sophonpanich"
]

_EXTRA_MALE_CHINESE = [
    "Wei", "Jun", "Lei", "Bo", "Hao", "Tao", "Ming", "Jian", "Qiang", "Peng",
    "Gang", "Bin", "Chao", "Feng", "Yong", "Xin", "Yu", "Jie", "Liang", "Zhen",
    "Kai", "Cheng", "Rui", "Hang", "Shuai", "Zhe", "Hui", "Xiang", "Lin", "Yang",
    "Fan", "Sen", "Kun", "Yuan", "Hong", "Dong", "Jin", "Bao", "Sheng", "Zhi",
    "Long", "Tian", "Yue", "Quan", "Yan", "Qing", "Song", "Ping", "Guo", "Xuan",
    "Haoran", "Yuxuan", "Zihan", "Yichen", "Yize", "Zixuan", "Haoyu", "Yinuo", "Mingze", "Yuchen"
]

_EXTRA_FEMALE_CHINESE = [
    "Fang", "Jing", "Na", "Min", "Li", "Juan", "Yan", "Xiu", "Ling", "Ying",
    "Xia", "Lan", "Ting", "Ping", "Hong", "Mei", "Dan", "Fen", "Qian", "Yun",
    "Hui", "Zhen", "Lin", "Qin", "Yue", "Jia", "Xue", "Shuang", "Qing", "Fei",
    "Rui", "Shan", "Lu", "Meng", "Yuan", "Yi", "Xin", "Ke", "Wei", "Jie",
    "Yu", "Xuan", "Hao", "Wen", "Le", "Ning", "Chun", "Xiao", "Ya", "Yiting",
    "Yuxin", "Xinyi", "Yinuo", "Zixuan", "Jiayi", "Yuhan", "Mengqi", "Ruoxi", "Yiran", "Kexin"
]

_EXTRA_LAST_CHINESE = [
    "Wang", "Li", "Zhang", "Liu", "Chen", "Yang", "Huang", "Zhao", "Wu", "Zhou",
    "Xu", "Sun", "Ma", "Zhu", "Hu", "Guo", "He", "Gao", "Lin", "Luo",
    "Zheng", "Liang", "Xie", "Song", "Tang", "Xu", "Han", "Feng", "Deng", "Cao",
    "Peng", "Zeng", "Xiao", "Tian", "Dong", "Yuan", "Pan", "Yu", "Jiang", "Cai",
    "Yu", "Du", "Ye", "Cheng", "Su", "Wei", "Lu", "Ding", "Ren", "Shen"
]

_EXTRA_MALE_KOREAN = [
    "Min-jun", "Seo-jun", "Do-yun", "Ye-jun", "Si-woo", "Ha-joon", "Ju-won", "Ji-ho", "Ji-hu", "Jun-seo",
    "Jun-woo", "Do-hyun", "Geon-woo", "Woo-jin", "Hyun-woo", "Seon-woo", "Min-jae", "Yu-jun", "Yeon-woo", "Si-yoon",
    "Dong-hyun", "Jung-woo", "Tae-yoon", "Eun-woo", "Jin-woo", "Ji-hoon", "Sung-min", "Min-kyu", "Seung-woo", "Hyun-seok",
    "Jae-won", "Sang-min", "Tae-hyun", "Young-min", "Ki-bum", "Kwang-soo", "Dae-sung", "Dong-wook", "Myung-hoon", "Bo-gum"
]

_EXTRA_FEMALE_KOREAN = [
    "Seo-yeon", "Seo-yun", "Ji-woo", "Seo-hyun", "Ha-eun", "Ha-yun", "Min-seo", "Ji-yoo", "Yun-seo", "Ji-min",
    "Chae-won", "Su-ah", "Da-eun", "Ye-eun", "Ji-a", "So-yul", "Eun-seo", "Yu-na", "Ye-rin", "Si-eun",
    "Ha-rin", "So-eun", "Chae-eun", "Na-eun", "Su-bin", "Ah-in", "Ye-won", "Ga-eun", "So-yeon", "Bo-min",
    "Eun-ji", "Hye-jin", "Min-ji", "Ji-hye", "Soo-jin", "Yu-jin", "Seon-young", "Jung-eun", "Mi-kyung", "Young-hee"
]

_EXTRA_LAST_KOREAN = [
    "Kim", "Lee", "Park", "Choi", "Jung", "Kang", "Cho", "Yoon", "Jang", "Lim",
    "Han", "Oh", "Seo", "Shin", "Kwon", "Hwang", "Ahn", "Song", "Ryu", "Hong",
    "Ko", "Moon", "Yang", "Son", "Bae", "Baek", "Huh", "Yoo", "Nam", "Shim",
    "Roh", "Ha", "Kwak", "Sung", "Cha", "Ju", "Woo", "Koo", "Im", "Jeon"
]

# Tich hop an toan vao cac danh sach goc
for _name in _EXTRA_MALE_INDIAN:
    if _name not in FIRST_NAMES_MALE_INDIAN: FIRST_NAMES_MALE_INDIAN.append(_name)
for _name in _EXTRA_FEMALE_INDIAN:
    if _name not in FIRST_NAMES_FEMALE_INDIAN: FIRST_NAMES_FEMALE_INDIAN.append(_name)
for _name in _EXTRA_LAST_INDIAN:
    if _name not in LAST_NAMES_INDIAN: LAST_NAMES_INDIAN.append(_name)

for _name in _EXTRA_MALE_THAI:
    if _name not in FIRST_NAMES_MALE_THAI: FIRST_NAMES_MALE_THAI.append(_name)
for _name in _EXTRA_FEMALE_THAI:
    if _name not in FIRST_NAMES_FEMALE_THAI: FIRST_NAMES_FEMALE_THAI.append(_name)
for _name in _EXTRA_LAST_THAI:
    if _name not in LAST_NAMES_THAI: LAST_NAMES_THAI.append(_name)

for _name in _EXTRA_MALE_CHINESE:
    if _name not in FIRST_NAMES_MALE_CHINESE: FIRST_NAMES_MALE_CHINESE.append(_name)
for _name in _EXTRA_FEMALE_CHINESE:
    if _name not in FIRST_NAMES_FEMALE_CHINESE: FIRST_NAMES_FEMALE_CHINESE.append(_name)
for _name in _EXTRA_LAST_CHINESE:
    if _name not in LAST_NAMES_CHINESE: LAST_NAMES_CHINESE.append(_name)

for _name in _EXTRA_MALE_KOREAN:
    if _name not in FIRST_NAMES_MALE_KOREAN: FIRST_NAMES_MALE_KOREAN.append(_name)
for _name in _EXTRA_FEMALE_KOREAN:
    if _name not in FIRST_NAMES_FEMALE_KOREAN: FIRST_NAMES_FEMALE_KOREAN.append(_name)
for _name in _EXTRA_LAST_KOREAN:
    if _name not in LAST_NAMES_KOREAN: LAST_NAMES_KOREAN.append(_name)


# ==============================================================================
# BỔ SUNG DỮ LIỆU TÊN ĐA QUỐC GIA ĐỒ SỘ (MASSIVE EXPANDED DATASETS)
# Ấn Độ, Thái Lan, Trung Quốc, Hàn Quốc, Nhật Bản, Tây (US-UK), Việt Nam
# ==============================================================================

_MORE_MALE_INDIAN = [
    "Vihaan", "Aditya", "Sai", "Reyansh", "Muhammad", "Arjun", "Reyansh", "Krishna", "Ishaan", "Shaurya",
    "Atharv", "Advik", "Pranav", "Advaith", "Aaryav", "Dhruv", "Kabir", "Ritvik", "Darsh", "Kian",
    "Rudra", "Om", "Samar", "Devansh", "Parth", "Ansh", "Laksh", "Ranveer", "Veer", "Naksh",
    "Ayush", "Tanmay", "Agastya", "Tejas", "Akshay", "Karan", "Kunal", "Siddharth", "Gaurav", "Manish",
    "Nikhil", "Pankaj", "Prashant", "Rajesh", "Ramesh", "Sanjay", "Sunil", "Vikram", "Vivek", "Yash",
    "Deepak", "Alok", "Anand", "Chandan", "Girish", "Harish", "Jayant", "Kamal", "Lalit", "Mahesh",
    "Naresh", "Pawan", "Rakesh", "Suresh", "Tarun", "Umesh", "Vinod", "Yogesh", "Brijesh", "Dinesh",
    "Ganesh", "Hemant", "Jagdish", "Kailash", "Mukesh", "Naveen", "Pramod", "Rajiv", "Satish", "Trilok",
    "Bhanu", "Chirag", "Devendra", "Eshwar", "Fateh", "Giridhar", "Himanshu", "Inder", "Jitendra", "Kuldeep",
    "Lokesh", "Madan", "Nitin", "Ojas", "Piyush", "Raghav", "Sameer", "Tushar", "Utkarsh", "Varun"
]

_MORE_FEMALE_INDIAN = [
    "Aadhya", "Saanvi", "Ananya", "Diya", "Gauri", "Anika", "Navya", "Angel", "Pari", "Myra",
    "Avani", "Isha", "Riya", "Aarohi", "Anvi", "Kavya", "Ahana", "Sia", "Khushi", "Sara",
    "Anaya", "Prisha", "Aditi", "Arya", "Sneha", "Tanvi", "Vanya", "Trisha", "Kiara", "Shanaya",
    "Meera", "Rhea", "Nandini", "Tara", "Samaira", "Simran", "Pooja", "Neha", "Divya", "Swati",
    "Shreya", "Kajal", "Ritu", "Alka", "Sunita", "Anita", "Geeta", "Rekha", "Suman", "Kiran",
    "Preeti", "Mamta", "Seema", "Archana", "Chaya", "Deepika", "Garima", "Jyoti", "Lata", "Madhu",
    "Nisha", "Payal", "Radha", "Shikha", "Usha", "Vimla", "Yamuna", "Bhavna", "Damini", "Ekta",
    "Gunjan", "Harsha", "Indu", "Jaya", "Kusum", "Leela", "Meenakshi", "Nirmala", "Pallavi", "Rashmi",
    "Sarita", "Tripti", "Urvi", "Varsha", "Yashoda", "Babita", "Champa", "Deepa", "Gayatri", "Hema"
]

_MORE_LAST_INDIAN = [
    "Chatterjee", "Banerjee", "Bose", "Ghosh", "Mukhopadhyay", "Bandyopadhyay", "Chattopadhyay", "Ganguly",
    "Iyer", "Iyengar", "Nair", "Menon", "Pillai", "Kurup", "Panicker", "Warrier", "Nambiar", "Marar",
    "Reddy", "Rao", "Naidu", "Chowdary", "Goud", "Yadav", "Raju", "Varma", "Kamma", "Kapu",
    "Shetty", "Rai", "Hegde", "Alva", "Bhandary", "Pujari", "Karkera", "Kotian", "Amin", "Salian",
    "Deshmukh", "Patil", "Pawar", "Jadhav", "Shinde", "Kadam", "Sawant", "Chavan", "Bhosle", "More",
    "Trivedi", "Pandya", "Vyas", "Dave", "Jani", "Upadhyay", "Shukla", "Pandey", "Mishra", "Tiwari",
    "Dubey", "Chaubey", "Tripathi", "Pathak", "Awasthi", "Bajpai", "Dixit", "Ojha", "Dwivedi", "Chaturvedi"
]

_MORE_MALE_THAI = [
    "Akkarapol", "Anusorn", "Apisit", "Arak", "Arthit", "Athiwat", "Banyat", "Boonprasert", "Chaowalit", "Charoenchai",
    "Chatchawan", "Chatuporn", "Chirawat", "Chusak", "Danai", "Ekachai", "Issara", "Itthiphol", "Jakkrit", "Jaturong",
    "Jetsada", "Kanchit", "Kasem", "Kitti", "Komet", "Kosin", "Kriangkrai", "Manit", "Montri", "Narong",
    "Narongrit", "Nattawat", "Nawat", "Nipon", "Niran", "Noppadol", "Pakorn", "Panupong", "Parinya", "Pasakorn",
    "Phanu", "Phichit", "Phongthep", "Phongsatorn", "Pichai", "Pipat", "Pirote", "Pongpat", "Pongsak", "Pracha",
    "Pramuan", "Prasit", "Prayoon", "Preechayan", "Rachen", "Rattana", "Rawat", "Sakchai", "Samran", "Santi",
    "Sarawut", "Satit", "Seksan", "Sirichai", "Sirote", "Somkiet", "Somnuk", "Songpol", "Songsak", "Suchart",
    "Sudjit", "Sukit", "Sumet", "Supachai", "Suphol", "Surachai", "Surasak", "Suthep", "Suwit", "Tawatchai",
    "Teerachai", "Teerapat", "Teerasak", "Thada", "Thaksin", "Thammanoon", "Theerawat", "Thirawat", "Thongchai", "Udom",
    "Varut", "Vichai", "Viroj", "Voravit", "Wanchai", "Warakorn", "Warut", "Wichian", "Winai", "Yongyuth"
]

_MORE_FEMALE_THAI = [
    "Amara", "Anchalee", "Angkana", "Anocha", "Apinya", "Areerat", "Benjamas", "Busaba", "Chada", "Chalisa",
    "Champee", "Chanida", "Chantana", "Charanya", "Chatchadaporn", "Chayanin", "Chuleeporn", "Duangdao", "Duangjai", "Duangruedee",
    "Jantira", "Jarunee", "Jidapa", "Jintana", "Jiraporn", "Kamonchanok", "Kanchana", "Kannikar", "Karnjana", "Kasemsee",
    "Ketsuda", "Kittiya", "Kulwadee", "Laddawan", "Laksana", "Lalita", "Lamduan", "Maneerat", "Manee", "Mantana",
    "Mayura", "Monta", "Nantana", "Napaporn", "Nareerat", "Natacha", "Nattaporn", "Nattarika", "Nichada", "Nimnuan",
    "Nongkran", "Nonglak", "Nongyao", "Nuanchan", "Oranuch", "Paweena", "Peeraya", "Petchra", "Phatcharaporn", "Pichamon",
    "Pimchanok", "Pimpisut", "Ploychanok", "Pornpan", "Pornthida", "Pratum", "Premjit", "Puangpetch", "Pussadee", "Ratchanok",
    "Rosarin", "Rungthip", "Saengduean", "Saijai", "Samornrat", "Sangrawee", "Sansanee", "Saranya", "Sasiwimon", "Sineenat",
    "Sirilak", "Sirima", "Siripen", "Somchit", "Somrudee", "Sudaporn", "Sudarat", "Sujitra", "Sukanya", "Suleeporn",
    "Sunisa", "Suphaphorn", "Surang", "Suwanna", "Thanyarat", "Ubolrat", "Umporn", "Vanida", "Wandee", "Wanpen"
]

_MORE_LAST_THAI = [
    "Amornvivat", "Apirat", "Assavanond", "Banyatpiyaphod", "Boonyaratglin", "Chaiprasit", "Chaiyawan", "Charasvirot",
    "Chatchaval", "Chavalit", "Chintakanond", "Chokwatana", "Damrongkiat", "Intarathai", "Jirayus", "Kajornkiat",
    "Karnasuta", "Ketwongse", "Kittikachorn", "Krairiksh", "Lamsam", "Mahagitsiri", "Na-Ranong", "Nantapisal",
    "Nimmanahaeminda", "Osathanugrah", "Paorohitya", "Phara", "Phaisan", "Phornprapha", "Piyaoui", "Promphan",
    "Punyaratabandhu", "Rangsiyopas", "Ratanarak", "Rojanasangvorn", "Sahaviriya", "Sarasin", "Sasiprapha", "Sethaputra",
    "Siamwalla", "Sinpatanasakul", "Sirivadhanabhakdi", "Sompong", "Srichawla", "Sukhanetr", "Suriyabhivadh", "Tangmatitham",
    "Teepsuwan", "Tejavibulya", "Thienthai", "Trakulkasemsuk", "Ungsuprasert", "Vanich", "Vongkusolkit", "Wangspa",
    "Wattana", "Wattanasin", "Wongsarot", "Wongsuwan", "Worakul", "Yuthavong", "Zansern", "Bhumiratana"
]

_MORE_MALE_CHINESE = [
    "An", "Bai", "Bao", "Bin", "Bing", "Bohai", "Bowen", "Chang", "Chao", "Chen",
    "Cheng", "Cong", "Da", "Dali", "De", "Ding", "Dong", "En", "Fa", "Fan",
    "Fang", "Feng", "Fu", "Gang", "Gao", "Gen", "Geng", "Guang", "Gui", "Guo",
    "Hai", "Han", "Hao", "He", "Heng", "Hong", "Hou", "Hu", "Hua", "Huan",
    "Huang", "Hui", "Ji", "Jia", "Jian", "Jiang", "Jiao", "Jie", "Jin", "Jing",
    "Jiu", "Jun", "Kai", "Kang", "Ke", "Kuan", "Kui", "Kun", "Lan", "Lang",
    "Le", "Lei", "Li", "Lian", "Liang", "Liao", "Lin", "Ling", "Liu", "Long",
    "Lu", "Luan", "Lun", "Luo", "Mang", "Mao", "Mei", "Meng", "Mian", "Miao",
    "Min", "Ming", "Mo", "Nan", "Ning", "Niu", "Pan", "Pei", "Peng", "Pi",
    "Pian", "Ping", "Po", "Pu", "Qi", "Qian", "Qiang", "Qiao", "Qin", "Qing"
]

_MORE_FEMALE_CHINESE = [
    "Ai", "Bao", "Bei", "Bi", "Bin", "Bing", "Bo", "Cai", "Can", "Cao",
    "Cha", "Chai", "Chan", "Chang", "Chao", "Che", "Chen", "Cheng", "Chi", "Chong",
    "Chou", "Chu", "Chuan", "Chun", "Ci", "Cong", "Cui", "Da", "Dai", "Dan",
    "Dang", "Dao", "De", "Deng", "Di", "Dian", "Diao", "Die", "Ding", "Dong",
    "Dou", "Du", "Duan", "Duo", "E", "En", "Er", "Fa", "Fan", "Fang",
    "Fei", "Fen", "Feng", "Fu", "Gai", "Gan", "Gang", "Gao", "Ge", "Gen",
    "Geng", "Gou", "Gu", "Gua", "Guai", "Guan", "Guang", "Gui", "Gun", "Guo",
    "Ha", "Hai", "Han", "Hang", "Hao", "He", "Hei", "Hen", "Heng", "Hong",
    "Hou", "Hu", "Hua", "Huai", "Huan", "Huang", "Hui", "Hun", "Huo", "Ji",
    "Jia", "Jian", "Jiang", "Jiao", "Jie", "Jin", "Jing", "Jiong", "Jiu", "Ju"
]

_MORE_LAST_CHINESE = [
    "Jiang", "Shen", "Han", "Lu", "Tang", "Zheng", "Fang", "Yuan", "Qian", "Dai",
    "Long", "Tao", "Kong", "Mao", "Yin", "Xue", "Shi", "Xing", "Ji", "Gong",
    "Duan", "Lei", "He", "Meng", "Shao", "Qiu", "Wan", "Bai", "Kang", "Niu",
    "Mo", "Hong", "Cui", "Guan", "Jin", "Tan", "Gu", "Liao", "Hao", "Qiao",
    "Jia", "Lu", "Qin", "Pan", "Zou", "Xia", "Yan", "Bai", "Xiong", "Yao"
]

_MORE_MALE_KOREAN = [
    "Baek-hyeon", "Beom-seok", "Bo-kyung", "Byung-hun", "Byung-chul", "Chan-woo", "Chang-min", "Chi-won", "Chul-soo", "Dae-hyun",
    "Dong-gun", "Dong-jun", "Dong-sun", "Eun-hyuk", "Gwang-min", "Ha-neul", "Hae-jin", "Hee-chul", "Ho-seok", "Hong-gi",
    "Hoon", "Hye-sung", "Hyuk", "Hyun-bin", "Hyun-sik", "Il-sung", "In-pyo", "Jae-beom", "Jae-hyuk", "Jae-seok",
    "Jae-wook", "Ji-sub", "Jin-hwan", "Jin-young", "Jong-in", "Jong-kook", "Jong-suk", "Joo-won", "Joon-ho", "Jung-hwan",
    "Jung-nam", "Kang-in", "Kwang-hee", "Kyu-hyun", "Min-hyuk", "Min-woo", "Myung-soo", "Nam-joon", "Sang-woo", "Se-hun",
    "Seung-gi", "Seung-heon", "Si-won", "Soo-hyun", "Suk-hoon", "Sun-woo", "Sung-gyu", "Sung-jae", "Sung-woong", "Tae-min",
    "Tae-yang", "Won-bin", "Woo-sung", "Ye-sung", "Yong-hwa", "Yoo-chun", "Yoon-seok", "Young-jae", "Young-kwang", "Yun-ho"
]

_MORE_FEMALE_KOREAN = [
    "Ah-reum", "Bora", "Bo-ram", "Bo-young", "Chae-young", "Da-hee", "Da-som", "Eun-bi", "Eun-chae", "Eun-hye",
    "Eun-jung", "Eun-kyung", "Eun-sook", "Ha-na", "Ha-neul", "Hae-won", "Hana", "Han-byul", "Hee-jin", "Hee-sun",
    "Hyo-jin", "Hyo-joo", "Hyo-rin", "Hyun-ah", "Hyun-joo", "In-na", "Jae-eun", "Ji-ae", "Ji-eun", "Ji-hyun",
    "Ji-won", "Ji-yeon", "Ji-young", "Jin-ah", "Jin-hee", "Joo-hyun", "Jung-ah", "Jung-hwa", "Min-ah", "Min-jung",
    "Min-sun", "Mi-ra", "Mi-ran", "Mi-so", "Mi-sun", "Na-ra", "Na-yeon", "Na-young", "Ri-in", "Sa-rang",
    "Seo-hee", "Seo-jin", "Seol-hyun", "Seon-ho", "Seul-gi", "So-dam", "So-hee", "So-min", "So-ra", "Soo-jin",
    "Soo-young", "Sun-hee", "Sun-mi", "Sung-kyung", "Tae-hee", "Tae-yeon", "Woo-ri", "Ye-eun", "Ye-ji", "Yeon-hee",
    "Yoo-jung", "Yoon-ah", "Young-ae", "Young-ja", "Yu-ri"
]

_MORE_LAST_KOREAN = [
    "Bong", "Byun", "Chae", "Do", "Eum", "Gim", "Gwon", "Hyun", "Jang", "Jeong",
    "Jin", "Kil", "Kong", "Kwon", "Ma", "Mok", "Myung", "Na", "No", "Pae",
    "Pang", "Pyo", "Ra", "Rim", "Sa", "Seok", "Seol", "Sin", "So", "Sohn",
    "Song", "Suh", "Sun", "Tak", "Uhm", "Wang", "Won", "Yeo", "Yeon", "You"
]

_MORE_MALE_JAPANESE = [
    "Akira", "Daisuke", "Daiki", "Genta", "Haruki", "Haruto", "Hayato", "Hideki", "Hikaru", "Hiroki",
    "Hiroshi", "Ichiro", "Itsuki", "Jun", "Junpei", "Kaito", "Kanata", "Kazuki", "Kazuma", "Kazuo",
    "Keigo", "Keisuke", "Keita", "Ken", "Kenji", "Kenta", "Kohei", "Koji", "Kosuke", "Kotaro",
    "Kyohei", "Makoto", "Masaki", "Masashi", "Masato", "Naoki", "Naoto", "Noboru", "Ren", "Riku",
    "Rikuto", "Ryoma", "Ryosuke", "Ryota", "Ryuto", "Satoshi", "Shingo", "Shinji", "Shota", "Shoya",
    "Shuhei", "Shunsuke", "So", "Sora", "Sota", "Taichi", "Taiga", "Taiki", "Takahiro", "Takashi",
    "Takato", "Takumi", "Takuya", "Tatsuya", "Tomoki", "Tomoya", "Tsubasa", "Tsuyoshi", "Wataru", "Yamato",
    "Yosuke", "Yudai", "Yugo", "Yuichi", "Yuji", "Yuki", "Yukio", "Yuma", "Yuto", "Yuya"
]

_MORE_FEMALE_JAPANESE = [
    "Aika", "Aimi", "Airu", "Akane", "Akari", "Akiho", "Amino", "Aoi", "Asuka", "Ayaka",
    "Ayame", "Ayano", "Chiaki", "Chie", "Chiharu", "Chika", "Chinatsu", "Chiyo", "Ema", "Emi",
    "Emiko", "Eri", "Erika", "Fuka", "Fumiko", "Hana", "Hanako", "Haruka", "Haruko", "Haruna",
    "Hikari", "Hina", "Hinata", "Hiroko", "Hitomi", "Honoka", "Ichika", "Kaho", "Kana", "Kanna",
    "Kaori", "Kasumi", "Keiko", "Koharu", "Kokona", "Kotone", "Kumi", "Kumiko", "Mai", "Maki",
    "Makiko", "Mami", "Mana", "Manami", "Mao", "Marina", "Mariko", "Mayu", "Mayumi", "Megumi",
    "Mei", "Michiko", "Midori", "Miku", "Minami", "Mio", "Misaki", "Misato", "Mitsuha", "Miu",
    "Miwa", "Miyabi", "Miyu", "Miyuki", "Mizuki", "Moeka", "Momoka", "Momoko", "Nanami", "Nao"
]

_MORE_LAST_JAPANESE = [
    "Abe", "Aoki", "Endo", "Fujii", "Fujimoto", "Fujita", "Fukuda", "Goto", "Hara", "Hasegawa",
    "Hashimoto", "Hayashi", "Ikeda", "Inoue", "Ishida", "Ishihara", "Ishii", "Ishikawa", "Ito", "Iwamoto",
    "Iwasaki", "Kaneko", "Kato", "Kimura", "Kinoshita", "Kobayashi", "Kondo", "Koyama", "Kudo", "Maeda",
    "Maruyama", "Matsuda", "Matsui", "Matsumoto", "Matsuo", "Matsuoka", "Matsushita", "Miura", "Miyake", "Miyamoto",
    "Miyazaki", "Mori", "Morita", "Murakami", "Murata", "Nagai", "Nakagawa", "Nakajima", "Nakamura", "Nakano",
    "Nakashima", "Nakayama", "Nishida", "Nishikawa", "Nishimura", "Noda", "Nomura", "Ogawa", "Okada", "Okamoto",
    "Okazaki", "Ono", "Ota", "Otsuka", "Saito", "Sakai", "Sakamoto", "Sakurai", "Sano", "Sasaki",
    "Sato", "Shibata", "Shimizu", "Sugawara", "Sugimoto", "Sugiyama", "Suzuki", "Takada", "Takagi", "Takahashi",
    "Takeda", "Takeuchi", "Tamura", "Tanaka", "Taniguchi", "Uchida", "Ueda", "Ueno", "Wada", "Watanabe",
    "Yamada", "Yamaguchi", "Yamamoto", "Yamanaka", "Yamashita", "Yamazaki", "Yokoyama", "Yoshida", "Yoshikawa", "Yoshimoto"
]

# Tự động gộp vào các danh sách chính
for _lst, _more in [
    (FIRST_NAMES_MALE_INDIAN, _MORE_MALE_INDIAN),
    (FIRST_NAMES_FEMALE_INDIAN, _MORE_FEMALE_INDIAN),
    (LAST_NAMES_INDIAN, _MORE_LAST_INDIAN),
    (FIRST_NAMES_MALE_THAI, _MORE_MALE_THAI),
    (FIRST_NAMES_FEMALE_THAI, _MORE_FEMALE_THAI),
    (LAST_NAMES_THAI, _MORE_LAST_THAI),
    (FIRST_NAMES_MALE_CHINESE, _MORE_MALE_CHINESE),
    (FIRST_NAMES_FEMALE_CHINESE, _MORE_FEMALE_CHINESE),
    (LAST_NAMES_CHINESE, _MORE_LAST_CHINESE),
    (FIRST_NAMES_MALE_KOREAN, _MORE_MALE_KOREAN),
    (FIRST_NAMES_FEMALE_KOREAN, _MORE_FEMALE_KOREAN),
    (LAST_NAMES_KOREAN, _MORE_LAST_KOREAN),
    (FIRST_NAMES_MALE_JAPANESE, _MORE_MALE_JAPANESE),
    (FIRST_NAMES_FEMALE_JAPANESE, _MORE_FEMALE_JAPANESE),
    (LAST_NAMES_JAPANESE, _MORE_LAST_JAPANESE),
]:
    for _n in _more:
        if _n not in _lst:
            _lst.append(_n)
