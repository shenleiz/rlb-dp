import math
import FunctionLibrary.StringOperation
import DataPath

budget_parameter = 1 / 2
campaign = "3476"
laplace = 1
max_market_price = 300

click_num = 0
win_num = 0
ctr = 0.001

market_price_counter = [0] * (max_market_price + 1)
market_price_distribution = [1 / (max_market_price + 1)] * (max_market_price + 1)

hidden_click_num = 0

dimension = 0
weights = []

Dt_b_points = []
St = []
approx_model = []


def sigmoid(p):
	if p < -700:
		return 0
	return 1.0 / (1.0 + math.exp(-p))


def update_market_price_distribution_counter():
	global market_price_distribution, market_price_counter, laplace, win_num, max_market_price
	for i in range(0, max_market_price + 1):
		market_price_distribution[i] = (market_price_counter[i] + laplace) / (
		win_num + (max_market_price + 1) * laplace)


def update_click_rate():
	global click_num, win_num, ctr

	if win_num > 0 and click_num > 0:
		ctr = click_num / win_num
	else:
		ctr = 0.001


# KPI prediction function
def theta(x):
	global weights
	res = 0
	for index in x:
		res += weights[index]
	return sigmoid(res)


def load_derivative_value_function(campaign):
	global Dt_b_points, St, approx_model

	Dt_b_points = []
	St = []
	with open(DataPath.rtb_mdp_path + campaign + "/D_t_b_points.txt") as fin:
		for line in fin:
			line = line[:len(line) - 1].split("\t")
			num = int(line[1])
			st = int(line[2])
			points = []
			for i in range(num):
				points.append(float(line[3 + i]))
			Dt_b_points.append(points)
			St.append(st)
	with open(DataPath.rtb_mdp_path + campaign + "/D_t_b_weights.txt") as fin:
		line = fin.readline()
		line = line.split("\t")
		print(len(line))
		K = int((len(line) - 1) / 4)
		w_1_t = [0] * K
		w_1_b = [0] * K
		w_1_1 = [0] * K
		w_2 = [0] * (K + 1)
		for i in range(K):
			w_1_t[i] = float(line[i])
			w_1_b[i] = float(line[i + K])
			w_1_1[i] = float(line[i + 2 * K])
		for i in range(K + 1):
			w_2[i] = float(line[i + 3 * K])
		approx_model = [K, w_1_t, w_1_b, w_1_1, w_2]


def predict_D_t_b(t, b, K, w_1_t, w_1_b, w_1_1, w_2):
	z1 = [0] * (K + 1)
	for j in range(0, K):
		z1[j] = sigmoid(w_1_t[j] * t + w_1_b[j] * b + w_1_1[j])
	z1[K] = 1
	y = 0
	for j in range(K + 1):
		y += w_2[j] * z1[j]
	return y


def get_D_t_b(t, b):
	global Dt_b_points, St, approx_model

	if b < len(Dt_b_points[t]):
		return Dt_b_points[t][b]
	elif b >= St[t]:
		return 0
	else:
		predict = predict_D_t_b(t, b, approx_model[0], approx_model[1], approx_model[2], approx_model[3], approx_model[4])
		return max(0, predict)


def bid(bc, tc, x):
	global max_market_price
	take_action = 0
	theta_x = theta(x)
	for delta in range(0, min(bc, max_market_price) + 1):
		if delta == bc:
			take_action = bc
			break
		elif delta == max_market_price:
			take_action = max_market_price
			break
		else:
			theta_x -= get_D_t_b(tc - 1, bc - delta - 1)
			if theta_x < 0:
				take_action = delta
				break
	return take_action


def auction(line, b, t, period, B, T):
	global win_num, click_num, market_price_counter, \
		dimension, weights, budget_parameter, hidden_click_num
	line = line[0:len(line) - 1].split(" ")
	click = int(line[0])
	price = int(line[1])
	x = []
	for i in range(2, len(line)):
		x.append(int(line[i].split(":")[0]))
	action = bid(b, t, x)

	record = FunctionLibrary.StringOperation.getTime() + "\t{0}\t{1}_{2}\t{3}_{4}_{5}\t{6}_{7}_{8}\t".format(
		period, B, T, action, price, click, hidden_click_num, click_num, win_num)
	print(record)
	log.write(record + "\n")

	if action >= price:
		win_num += 1
		market_price_counter[price] += 1

		if click == 1:
			click_num += 1
		b -= price
		B -= price
	else:
		take_this_place = 1
	update_market_price_distribution_counter()
	update_click_rate()
	t -= 1
	T -= 1
	if click == 1:
		hidden_click_num += 1
	return b, t, B, T


def rtb_mdp(campaign):
	global win_num, click_num, market_price_counter, \
		dimension, weights, budget_parameter, hidden_click_num, value_function
	# load history data
	cost = 0
	with open(DataPath.rtb_mdp_path + campaign + "/" + DataPath.rtb_history_name) as fin:
		fin.readline()
		for line in fin:
			line = line[:len(line) - 1].split(" ")
			click = int(line[0])
			price = int(line[1])

			win_num += 1
			cost += price
			market_price_counter[price] += 1
			if click == 1:
				click_num += 1
	hidden_click_num = click_num
	update_market_price_distribution_counter()
	update_click_rate()
	budget = cost / win_num * budget_parameter

	# load logistic regression weights
	with open(DataPath.rtb_mdp_path + campaign + "/" + DataPath.lg_weight_name) as fin:
		line = fin.readline()
		line = line[:len(line) - 1].split("\t")
		dimension = len(line)
		for item in line:
			weights.append(float(item))

	# start test
	Ts = 10000
	print(FunctionLibrary.StringOperation.getTime() + "\ttest start")
	load_derivative_value_function(campaign)
	with open(DataPath.rtb_mdp_path + campaign + "/test.rtb.txt") as fin:
		line = fin.readline()
		line = line[:len(line) - 1].split("\t")
		T = int(line[1])
		B = 0
		period = 0
		sub_period_num = 0
		remaining_sub_period_num = 0

		t = 0
		b = 0
		bs = 0
		ts = 0
		for line in fin:
			if t == 0:
				line = line[:len(line) - 1].split("\t")
				period = int(line[0])
				B = int(budget * T)
				t = T
				b = B
				if period == 1:
					#load_derivative_value_function_full(int(b / t * Ts), Ts, campaign)
					sub_period_num = int(T / Ts)
				ts = Ts
				bs = int(B / sub_period_num)
				remaining_sub_period_num = sub_period_num
			else:
				(bs, ts, b, t) = auction(line, bs, ts, period, b, t)
				if ts == 0:
					if t == 0:
						continue
					remaining_sub_period_num -= 1
					ts = Ts
					bs = int(b / remaining_sub_period_num)


if __name__ == "__main__":
	log = open(DataPath.projectPath + "log/" + campaign + "-seg_D_t_b.log", "w")
	print(FunctionLibrary.StringOperation.getTime() + "\t" + campaign + "\tstart")
	log.write(FunctionLibrary.StringOperation.getTime() + "\t" + campaign + "\tstart\n")
	rtb_mdp(campaign)
	log.close()
